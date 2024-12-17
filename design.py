# vim: set shiftwidth=2 softtabstop=2 ts=2 expandtab:

import optparse
import os
import collections
import math
from enum import Enum
from optparse import OptionParser
import re

import circuit
import circuit_writer
import spef
import spice
import spice_analyser
import verilog


class Design():
  def __init__(self):
    self.top = None
  
    # The list of modules for which we have definitions. The first key is the
    # module's name and the second key is the path (absolute) in which it was
    # defined.
    self.modules_by_name_then_path = collections.defaultdict(dict)

    # A list of unknown modules (black boxes). Values are circuit.ExternalModules.
    self.external_modules = {}

    # Lists of pairs of (path, instance name) for a given module name recording
    # instantiations of the given module at the given path (which could be
    # None, if this is not known).
    self.unknown_references = collections.defaultdict(list)

    self.external_modules[circuit.CAPACITOR.name] = circuit.CAPACITOR
    self.external_modules[circuit.RESISTOR.name] = circuit.RESISTOR
    self.external_modules[circuit.INDUCTOR.name] = circuit.INDUCTOR
    self.power_net_names = ['VDD', 'VPWR']
    self.ground_net_names = ['VSS', 'VGND']

  def AddModule(self, module_name, module, path=None):
    try:
      previous_defs = self.modules_by_name_then_path[module_name]
      existing = previous_defs[path]
      raise Exception(f'Duplicate definition of {module_name} at path {path}')
    except KeyError:
      # No previous definitions.
      pass
    self.modules_by_name_then_path[module_name][path] = module

  # Look up a module by name and optionally file path. If there are multiple
  # definitions for a module, return any of them.
  # TODO(growly): It might be nice to guarantee that we return the first
  # definition up the path hierarchy, to help with matching definitions in
  # different soruces (e.g. one in verilog and the other in SPEF).
  def GetModule(self, module_name, path=None):
    if module_name not in self.modules_by_name_then_path:
      return None
    definitions = self.modules_by_name_then_path[module_name]
    if len(definitions) == 1:
      return list(definitions.values())[0]

    if path is None:
      print(f'Multiple definitions exist for {module_name}, but no path was '
            'given for the source of the reference. Picking the first one.')
      return list(definitions.values())[0]
  
    # If there's an exact match (same file, presumably), return it.
    if path in definitions:
      return definitions[path]

    # Otherwise, find the definition whose path has the longest common prefix
    # with the requestor path.
    print(f'Multiple definitions exist for {module_name}, path={path}, '
          'picking longest common prefix')

    # The second key is the length of the common prefix between the searched 
    other_paths = [
        (p, len(os.path.commonprefix(path, p))) for p in definitions.keys()]
    other_paths.sort(other_paths, key=lambda x: x[1])
    print(other_paths)
    return other_paths[0][0]

  def FindTop(self, use_name):
    if use_name is None:
      # Can find top, but not worth convenience.
      raise NotImplementedError('will not find top today')
    try:
      top = self.GetModule(use_name)
      self.top = top
      return top
    except:
      return None

  # It's possible when merging definitions for various modules, which have been
  # created independently, that there will arise conflicting module names. This
  # happens, for example, when macros are hardened separately by flows that
  # create locally-significant modules like "my_mux", which differe among
  # macros, but which all share the name "my_mux". We rely on a
  # longest-common-prefix-based lookup to find the appropriate reference when
  # parsing these from Verilog, and ??? when parsing SPEF.
  #
  # Anyway, when all is said and done, we can make the design sane by generating
  # unique names for each of these overloaded modules.
  def MakeModulesUnique(self):
    new_modules_dict = collections.defaultdict(dict)

    # 1. Find all modules with multiple definitions.
    for module_name, definitions in self.modules_by_name_then_path.items():
      if len(definitions) < 2:
        new_modules_dict[module_name] = definitions
        continue

      count = 0
      for path, module in definitions.items():
        old_name = module.name
        module.name = f'{old_name}_{count}'
        count += 1
        new_modules_dict[module.name][path] = module
        print(f'renamed {old_name} -> {module.name}')

    # 2. Check that all instances have correct names for their instantiated
    # modules. I'm not actually sure why this field of Instance exists, but
    # whatever.
    for module_name, definitions in self.modules_by_name_then_path.items():
      for path, module in definitions.items():
        for instance_name, instance in module.instances.items():
          if instance.module is not None and (
              instance.module_name != instance.module.name):
            instance.module_name = instance.module.name

    self.modules_by_name_then_path = new_modules_dict

  def ParseVerilog(self, verilog_files, include_paths, defines):
    return verilog.DesignReader.ParseVerilog(
      design=self,
      verilog_files=verilog_files, 
      include_paths=include_paths, 
      defines=defines
    )

  def Link(self):
    # At this point, every module we should know about *should* be available to
    # us. Replace every unknown reference with a black box.
    for name, instances in self.unknown_references.items():
      for path, instance in instances:
        internal_module = self.GetModule(name, path)
        if internal_module is not None:
          # Module has since been loaded.
          assert(instance.module_name == name)
          instance.module = internal_module

          if name in self.external_modules:
            del self.external_modules[name]
          continue
        elif name in self.external_modules:
          # Nothing to do.
          continue

      # Create an external module.
      external_module = circuit.ExternalModule()
      external_module.name = name
      # TODO(growly): Driving by, this doesn't do anything. It should do
      # something or be removed.
      # external_module.GuessPorts(instances)
      self.external_modules[name] = external_module

    for definitions in self.modules_by_name_then_path.values():
      for path, module in definitions.items():
        for _, instance in module.instances.items():
          ref_name = instance.module_name
          module = self.GetModule(ref_name, path=path)
          if module is None and ref_name in self.external_modules:
            module = self.external_modules[ref_name]
          if module is None:
            raise Exception('instance references module which should be known or '
                            'external, but is neither: "{}"'.format(ref_name))

          # Internal or external, we need one of those objects here.
          instance.module = module

          for i, signal in enumerate(instance.connections_by_order):
            if not module.port_order:
              print(f'warning: instance {instance.name} is of {instance.module_name} '
                    f'which has no known port_order')
              continue
            # Use the ordered connections to connect up ports, now that we know
            # what the master Module is.
            try:
                port_name = module.port_order[i]
            except IndexError:
                print(f'warning: instance {instance.name} of module '
                      f'{instance.module_name} has too many connections; signal '
                      f'{signal} will not be connected')
                known_ports = ', '.join(module.port_order)
                connections = ', '.join(
                    x.name for x in instance.connections_by_order)
                print(f'\tknown ports: {known_ports}\n'
                      f'\tinstance connections: {connections}')
                continue

            connection = circuit.Connection(port_name)
            connection.signal = signal
            connection.instance = instance
            instance.connections[port_name] = connection

  def ParseSPEF(self, spef_files):
    for f in spef_files:
      print(f'reading spef: {f}')
      spef_reader = spef.SPEFReader('VSS')
      module = spef_reader.ReadSPEF(f)
      self.AddModuleFromSPEF(module, path=f)

  def AddModuleFromSPEF(self, module, path=None):
    existing = self.GetModule(module.name)
    if existing is not None:
      # Have to do a merge/verification.
      print(f'merging module: {module.name}')
      self.MergeSPEFIntoVerilogModule(existing, module)
      del module
    else:
      print(f'adding module: {module.name}')
      self.AddModule(module.name, module)

  def CheckPowerAndGround(self):
    # Makes sure power and ground are connected.
    # TODO(growly): This needs to be a bit more robust. User should specify
    # what the power and ground nets are. Additionally, there may be other
    # implicit signals which we should be able to discover: clk, rst, etc.
    for module_name, definitions in self.modules_by_name_then_path.items():
      for path, module in definitions.items():
        for net in self.power_net_names + self.ground_net_names:
          if net in module.signals and not net in module.ports:
            print(f'creating {path}/{module_name} port for implicit net: {net}')
            signal = module.GetOrCreateSignal(net)
            new_port = circuit.Port()
            new_port.signal = signal
            new_port.direction = circuit.Port.Direction.NONE
            module.ports[net] = new_port
            module.port_order.insert(0, net)


  def MergeSPEFIntoVerilogModule(self, verilog_module, spef_module):
    assert(verilog_module.name == spef_module.name)
    # When trying to match components of one module to the other, there is the
    # general problem of graph isomorphism here which we will conveniently
    # avoid.
    #
    # There is also the easier problem of differencing two netlists just to
    # figure out that they are in fact different, a la LVS. This is not that.
    #
    # Subgraphs are equivalent if they start/end at the same ports on the same
    # instances. In that case, the bigger subgraph probably should replace the
    # smaller one.  But is this really more robust that just assuming the name
    # prefixes will be the same?
    #
    # We have to make some assumptions to make this easier:
    #   - port names, cell names, do not change
    #
    # So roughly, for each of the mergee and the merger,
    #   Go through all the instances:
    #     For each port, find the sub-graph to which it connects.
    #     The subgraph perimeter is those instances which appear in the mergee
    #     (original).
    #       Compare this sub-graph for both mergee and merger.
    #         Check if prefix assumptions hold.
    #
    # But actually we're not going to do any of that. We're going to assume
    # that the SPEF netlist includes hints about the Verilog netlist and we're
    # going to use them. And that the name mappings provide the original names
    # and that two things of the same name should be the same thing.
    #
    # TODO(growly): This is not generalised! You say you want nice things like
    # a way to merge two netlists from arbitrary sources but then you do things
    # like this!
    #
    # I think I'm being an idiot. This is sort of a half-generalised solution
    # that is neither general enough to be useful nor straight-forward enough
    # to be simple.
    #
    # TODO(growly): Can I just create a Module.replaced_nets that is populated
    # by SPEF files, assuming that every *D_NET entry does in fact fully
    # replace a net?

    # TODO(growly): This is correct behaviour:
    # Verilog will specify an input bus, say a[15:0]. Extraction will replace a
    # wire within that bus with another, say a.0:8, which is part of the
    # subnetwork found when extracting a[0]. Some ways to deal with this:
    # - delete 'a' and hope that the extraction is complete and includes
    #   extracted replacements for the other bus wires too; if 'a' is connected
    #   to by a fixed external port, split that port apart, explicitly
    #   flattening it into subsignals of width=1
    # - keep the original bus, and disconnect all signals but the port, then
    #   replace each subsignal with a concat as it is discovered: e.g. port a
    #   would normally connect to a[15:0] - on being presented with a.5 will
    #   turn into a concatenation of {a[15:6], a.5, a[4:0]}.
    # - some hybrid? port names must stay fixed, and their external behaviour
    #   remains that of a bus, so specify ports with their own width and
    #   provide an explicit mapping to internal signals from each port
    #   sub-index.
    # - the hack is to just replace each subwire with an additional port in the
    #   right place. This is tantamount to flattening buses at the input but in
    #   a hacky implicit way.
    #
    # This worked previously because even though we remove the port's signal
    # from signals dict, the signal remains associated with the port's 'signal'
    # attribute.
    #
    # So maybe step one is to give the Signal a 'connected_port', then use that
    # to modify the port. But then we'd need to keep some parent bookkeeping
    # signal around so that subsequent sub-wire definitions would know where to
    # look. This seems like option (2)...
    #
    # Hmmm. quick and dirty seems to associate the width of the port with the Port
    # permanently, so that it can be inferred. But that's basically suggesting
    # we do the concat thing.

    unseen_signals = set(verilog_module.signals.keys())
    unseen_instances = set(verilog_module.instances.keys())

    def MakeNewConnection(port_name, slice_or_signal):
      connection = circuit.Connection(port_name)
      if isinstance(slice_or_signal, circuit.Slice):
        signal = verilog_module.GetOrCreateSignal(slice_or_signal.signal.name)
        net_slice = circuit.Slice()
        net_slice.signal = signal
        net_slice.top = slice_or_signal.top
        net_slice.bottom = slice_or_signal.bottom
        # Every wire in the slice is connected to this connection.
        connection.slice = net_slice
        net_slice.Connect(connection)
      elif isinstance(slice_or_signal, circuit.Signal):
        signal = verilog_module.GetOrCreateSignal(slice_or_signal.name)
        connection.signal = signal
        signal.Connect(connection)
      else:
        raise NotImplementedError(
            'template_connection has slice and signal are both None')
      return connection

    # Merge signals.
    for name, new in spef_module.signals.items():
      if name in verilog_module.signals:
        existing = verilog_module.signals[name]
        if existing.width < new.width:
          # It's ok if the width we infer from the SPEF file is smaller than an
          # explicit existing width, because the SPEF file might not make
          # reference to all of the signal's wires. But widening an
          # explicitly-sized signal could be a bad sign.
          raise spef.SPEFBadAssumption(
              f'merging in signal {name} with greater width {new.width} vs '
              f'{existing.width}; existing defs in {verilog_module.paths}, new '
              f'in {spef_module.paths}')
        #existing = verilog_module.signals[name]
        #existing.Disconnect()
        #del verilog_module.signals[name]
        print(f'existing {existing}')
        unseen_signals.remove(name)
      elif new.parent_name and new.parent_name in verilog_module.signals:
        existing = verilog_module.signals[new.parent_name]
        # Disconnect from everything that isn't a port. This leaves the signal as
        # known so that we can create slices (references) to it again.
        print(f'disconnecting {existing}')
        existing.Disconnect()
        if existing.ports is None:
          # Replace existing signal's parent.
          print(f'deleting parent signal: {new.parent_name}')
          del verilog_module.signals[new.parent_name]
        else:
          # TODO(growly): This is a bit of a hack. See one of my essays in the
          # comments. Probably need to make SPEF extractor aware of slices. What
          # we do for now is just make sure the port's signal is not deleted,
          # so that subsequent references to 'a' for example do not create a
          # new 1-wire signal called 'a'. There is no relational connection in the
          # schema yet, though.
          pass
        # Stand up a reference to the new signal.
        copied_in = verilog_module.GetOrCreateSignal(name)
        copied_in.width = new.width
        print(f'new {copied_in} replaces {new.parent_name}')
        # Keep track of which signals we have in the existing module but that
        # we don't see in the new circuit.
        if new.parent_name in unseen_signals:
          unseen_signals.remove(new.parent_name)
      else:
        signal = verilog_module.GetOrCreateSignal(name)
        print(f'new {signal}')
        
    # Merge instances.
    for name, new in spef_module.instances.items():
      if name in verilog_module.instances:
        modify = verilog_module.instances[name]
        modify.parameters.update(new.parameters)
        print(f'existing [{name}] {modify}')
        if modify.module_name != new.module_name:
          raise Exception(
              f'merging in instance {name} with different module type '
              f'{new.module_name} vs {modify.module_name}')
        unseen_instances.remove(name)
      else:
        modify = circuit.Instance()
        modify.name = new.name
        modify.module_name = new.module_name
        modify.parameters.update(new.parameters)
        print(f'new {modify}')
        verilog_module.instances[name] = modify

    # Elaborate connections among instances with all signals and instances now
    # merged.
    for name, new in spef_module.instances.items():
      existing = verilog_module.instances[name]
      # Merge (replace) port connections.
      for port_name, template_connection in new.connections.items():
        new_connection = MakeNewConnection(
            port_name, template_connection.GetConnected())
        new_connection.instance = existing
        if port_name in existing.connections:
          existing_connection = existing.connections[port_name]
          # Remove references to this connection in the parent slice/signal.
          print(f'removing connection {existing_connection} from parent {existing_connection.instance.connections}')
          existing_connection.DisconnectFromParent(include_ports=True)
          # Remove this connection from the existing instance.
          existing_connection.Disconnect()
          print(f'existing {name} port {port_name} reconnected to {new_connection}')
        else:
          print(f'new {name} port {port_name} connection to {new_connection}')
        existing.connections[port_name] = new_connection

    # Do not count implicit nets as 'unseen', since we'll never see them, by
    # definition.
    unseen_signals = unseen_signals - set(
        self.power_net_names + self.ground_net_names)

    # Prune signals that may have been replaced without much mention:
    # NOTE(growly): if we assumed that nets were described 1:1, we could do this
    # immediately, since we'd know that a *D_NET existing for each net, say.
    for name in list(unseen_signals):
      signal = verilog_module.signals[name]
      if not signal.ConnectsAnything:
        print(f'pruning {signal}')
        del verilog_module.signals[name]
        unseen_signals.remove(name)
        continue

    print('unseen signals in merged-in Module: {}'.format(unseen_signals))
    print('unseen instances in merged-in Module: {}'.format(unseen_instances))

  def ParseSpiceDefinitions(self, spice_files, headers_only=False):
    for file_name in spice_files:
      parser = spice.SpiceReader(headers_only=headers_only)
      parser.Read(file_name)

      if headers_only:
        # The only thing we get from Spice headers is the port order for an
        # external module.
        for module_name, port_order in parser.port_order_by_module.items():
          if module_name in self.external_modules:
            module = self.external_modules[module_name]
            assert(module.name == module_name)
          else:
            module = circuit.ExternalModule()
            module.name = module_name
            self.external_modules[module_name] = module

          if module.port_order and module.port_order != port_order:
            raise RuntimeError(f'error: existing port order {module.port_order} vs new {port_order}')

          for port_name in port_order:
            # This will create a Port and associated Signal object and append
            # to the port order.
            module.GetOrCreatePort(port_name)

      else:
        for subckt in parser.subckts:
          module = subckt.ToModule(self)
          self.AddModule(module.name, module, path=file_name)

          for instance in module.instances.values():
            module = self.GetModule(instance.module_name, path=file_name)
            if module is None:
              self.unknown_references[instance.module_name].append(
                  (file_name, instance))


  def Show(self):
    print('design: ')
    print('{} known modules:'.format(len(self.modules_by_name_then_path)))
    for name, definitions in self.modules_by_name_then_path.items():
      print('- {}'.format(name))
      for path, module in definitions.items():
        print('    {}: {}'.format(path, module))
    print('{} external modules:'.format(len(self.external_modules)))
    for name, module in self.external_modules.items():
      print('- {}'.format(name))
      print('    {}'.format(module))


