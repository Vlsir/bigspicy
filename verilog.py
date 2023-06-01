"""
Verilog Reading via `pyverilog.vparser.ast`, transforming its AST nodes into 
`Design` and `Module` counterparts.
"""

from typing import List 
from pathlib import Path 
from warnings import warn 

from pyverilog.vparser import parser as verilog_parser
import pyverilog.vparser.ast as ast

# Local Imports 
from circuit import Module, VerilogIdentifier, Port, Instance, Connection, Slice, Assignment, Concatenation


class DesignReader:
  """ Read Verilog into a `Design`. 

  Not really a class in the sense of having instances, but more a namespace 
  for associated static methods. """
    
  @staticmethod
  def ParseVerilog(
      design: "Design", 
      verilog_files: List[Path], 
      include_paths: List[Path], 
      defines: List[Path]
    ):
    first, directives = verilog_parser.parse(verilog_files,
                                             preprocess_include=include_paths,
                                             preprocess_define=defines)
    # 'first' is a pyverilog.vparser.ast.Node
    queue = [first]
    modules = []
    while queue:
      node = queue.pop()
      if isinstance(node, ast.ModuleDef):
        # Circuit.Module will read the node and its children to parse the
        # Verilog.
        module = Module.FromVerilog(node)
        modules.append(module)
      #if node.attr_names:
      #  for attr in node.attr_names:
      #    print('attr: {}={}'.format(attr, getattr(node, attr)))
      for c in node.children():
        queue.append(c)

    # Tidy up references made to other modules.
    for module in modules:
      name = module.name
      if name in design.known_modules:
        raise Exception('duplicate definition of {}'.format(name))
        #print(f'warning! {name} is defined multiple times, and all but one '
        #      'definitions will be ignored!')
      design.known_modules[name] = module
      if name in design.unknown_references:
        del design.unknown_references[name]
      # Maybe we referenced it already.
      for _, instance in module.instances.items():
        if instance.module_name not in design.known_modules:
          design.unknown_references[instance.module_name].append(instance)


class ModuleReader:
  """ Read Verilog into a `Module`. 

  Not really a class in the sense of having instances, but more a namespace 
  for associated static methods. """
    
  @staticmethod
  def LoadAST(module: Module, ast_node: ast.Node):
    # Assume 'ast_node' is a pyverilog.vparser.ast.ModuleDef
    module.name = ast_node.name
    
    for child in ast_node.children():
      if isinstance(child, ast.Paramlist):
        # Params come in an ast.ParamList.
        ModuleReader.LoadParamList(module, child)
      # Ports come in an ast.PortList.
      elif isinstance(child, ast.Portlist):
        ModuleReader.LoadPortlist(module, child)
      elif isinstance(child, ast.Decl):
        # Of primary interest are 'Decl's, which are wires and buses.
        ModuleReader.LoadDecl(module, child)
      elif isinstance(child, ast.InstanceList):
        ModuleReader.LoadInstanceList(module, child)
      elif isinstance(child, ast.Assign):
        ModuleReader.LoadAssign(module, child)
      else:
        warn(f'skipping child: {child}')

  @staticmethod
  def LoadPointer(module: Module, ast_pointer: ast.Pointer):
    net_name = VerilogIdentifier(ast_pointer.var.name).raw
    signal = module.GetOrCreateSignal(net_name)
    assert isinstance(ast_pointer.ptr, ast.IntConst)
    index = int(ast_pointer.ptr.value)

    # Can't call it 'slice', it's a keyword.
    the_slice  = Slice()
    the_slice.signal = signal
    the_slice.top = index
    the_slice.bottom = index
    return the_slice

  @staticmethod
  def LoadPartselect(module: Module, ast_partselect: ast.Partselect):
    name = VerilogIdentifier(ast_partselect.var.name).raw
    signal = module.GetOrCreateSignal(name)
    assert isinstance(ast_partselect.msb, ast.IntConst)
    assert isinstance(ast_partselect.lsb, ast.IntConst)

    the_slice  = Slice()
    the_slice.signal = signal
    the_slice.top = int(ast_partselect.msb.value)
    the_slice.bottom = int(ast_partselect.lsb.value)
    return the_slice

  @staticmethod
  def LoadAssign(module: Module, ast_assign: ast.Assign):
    # Expect ast_assign.left to be an ast.Lvalue object, and ast_assign.right to
    # be an ast.Rvalue object.
    ast_left = ast_assign.left.var
    ast_right = ast_assign.right.var

    # The left and right sides of the assignment are assignable objects, meaning
    # they need to track the assignments they participate in for when we
    # traverse the graph later.

    left = None
    right = None

    if isinstance(ast_left, ast.Identifier):
      # Signal name, str.
      name = VerilogIdentifier(ast_left.name).raw
      signal = module.GetOrCreateSignal(name)
      left = signal
    elif isinstance(ast_left, ast.Pointer):
      # Signal with single index.
      left_slice = ModuleReader.LoadPointer(module, ast_left)
      left = left_slice
    elif isinstance(ast_left, ast.Partselect):
      # Signal slice with upper and lower bound.
      name = VerilogIdentifier(ast_left.var.name).raw
      left_slice = ModuleReader.LoadPartselect(module, ast_left)
      left = left_slice
    elif isinstance(ast_left, ast.LConcat):
      # LValue concatenation.
      raise NotImplementedError(
          f'left side of assignment is {type(ast_left)}, {ast_left=}')

    if isinstance(ast_right, ast.Identifier):
      # Signal name, str.
      name = VerilogIdentifier(ast_right.name).raw
      right = module.GetOrCreateSignal(name)
    elif isinstance(ast_right, ast.Pointer):
      # Signal with single index.
      right = ModuleReader.LoadPointer(module, ast_right)
    elif isinstance(ast_right, ast.Partselect):
      # Signal slice with upper and lower bound.
      name = VerilogIdentifier(ast_right.var.name).raw
      right = ModuleReader.LoadPartselect(module, ast_right)
    elif isinstance(ast_right, ast.Concat):
      # Concatenation.
      raise NotImplementedError(
          f'right side of assignment is {type(ast_right)}, {ast_right=}')

    assignment = Assignment(left, right)
    left.AddAssignment(assignment)
    right.AddAssignment(assignment)
    print(f'mapping {left} <=> {right}')
    module.assignments[assignment.left] = assignment

  # TODO(growly): Remove Verilog-specific builders from Module, which should be
  # an abstract data container. Put them in VerilogReader or some such, with a
  # ToModule() function that returns a Module description of the Verilog.
  @staticmethod
  def LoadPortlist(module: Module, ast_portlist):
    for child in ast_portlist.children():
      if not isinstance(child, ast.Port):
        continue
      name = VerilogIdentifier(child.name).raw
      _ = module.GetOrCreatePort(name, width=child.width or 1)

  @staticmethod
  def LoadDecl(module: Module, ast_decl):
    # ast.Decl declares an ast.Variable, only some of which are of interest.
    children = ast_decl.children()
    if len(children) > 1:
      raise NotImplementedError(
          'didn\'t expect there to be this many children on a Decl')
    child = children[0]

    name = VerilogIdentifier(child.name).raw
    signed = child.signed

    if isinstance(child, ast.Wire) or isinstance(child, ast.Reg):
      # Treat 'wire' and 'reg' declarations the same for our purposes.
      if name in module.ports:
        # It appears the PyVerilog AST produces both a port-type and a `Wire`
        # for signals which are declared as such, like so: `input clk; wire
        # clk;` 
        # In our data model these are one thing: the port. 
        # We *think* the port must be declared first, and so when this Verilog
        # syntax is used, the ultimate port-object will already be present in
        # our `ports`. In which case, nothing more to do here. 
        return
        
      assert(name not in module.signals)
      width = 1 if not child.width else int(
          child.width.msb.value) - int(child.width.lsb.value) + 1
      signal = module.GetOrCreateSignal(name, width=width)
      return
    
    # Else we assume it's an input, output, inout, etc.
    direction = Port.Direction.NONE
    if isinstance(child, ast.Input):
      direction = Port.Direction.INPUT
    elif isinstance(child, ast.Output):
      direction = Port.Direction.OUTPUT
    elif isinstance(child, ast.Inout):
      direction = Port.Direction.INOUT

    width = 1 if not child.width else int(
        child.width.msb.value) - int(child.width.lsb.value) + 1
    if name in module.ports:
      port = module.ports[name]
      assert port.signal is not None, (
          f'port {name} should have a signal by this point')
      # We accept that a decl can override the width and direction of a signal
      # since ports can be declared without widths or directions. If it does,
      # we have to fix up the old signal and reconnect everything that would
      # have been connected to the full bus.
      if port.signal.width is None or width > port.signal.width:
        print(f'port {name} widened to {width}')
        signal = port.signal
        signal.Disconnect(port)
        signal.width = width
        signal.Connect(port)

      assert (width == port.signal.width), (
          f'port {name} has signal width mismatch {port.signal} != {width}')
      if port.direction is None or port.direction == Port.Direction.NONE:
        port.direction = direction
        print(f'port {name} now has direction {direction}')
      assert (direction == port.direction), (
          f'port {name} has direction {port.direction} != {direction}')
    elif direction != Port.Direction.NONE:
      # This is not a known port, but it has a direction (i.e. the direction
      # isn't NONE), so perhaps it should be a port.
      _ = module.GetOrCreatePort(name, width=width, direction=direction)
      raise NotImplementedError('wow I can\'t believe this happened')
  
  @staticmethod
  def LoadInstanceList(module: Module, ast_instancelist):
    module_name = ast_instancelist.module
    for ast_instance in ast_instancelist.instances:
      instance = Instance()
      instance.name = VerilogIdentifier(ast_instance.name).raw
      instance.module_name = VerilogIdentifier(ast_instance.module).raw
      if not ast_instance.portlist:
        #print('skipping instance without connections: {}'.format(instance))
        del instance
        continue
      for ast_portarg in ast_instance.portlist:
        # These are connections.
        port_name = ast_portarg.portname
        connection = Connection(port_name)
        connection.instance = instance
        children = ast_portarg.children()
        if len(children) > 1:
          raise NotImplementedError(
              'can\'t deal with portargs that have many children')
        # If the argname is None, the port is not connected to anything, it is
        # just written. We can ignore it since we do not explicitly encode
        # disconnections.
        if len(children) == 0:
          print(f'instance {instance.name} ({module_name}) port '
                f'{ast_portarg.portname} is disconnected, skipping')
          continue
        identifier = children[0]
        if isinstance(identifier, ast.Identifier):
          net_name = VerilogIdentifier(identifier.name).raw
          signal = module.signals[net_name]
          connection.signal = signal
          signal.Connect(connection)
        elif isinstance(identifier, ast.Pointer):
          net_slice = ModuleReader.LoadPointer(module, identifier)
          net_slice.Connect(connection)
          connection.slice = net_slice
        elif isinstance(identifier, ast.Concat):
          parts = []
          for child in identifier.list:
            if isinstance(child, ast.Identifier):
              net_name = VerilogIdentifier(child.name).raw
              signal = module.GetOrCreateSignal(net_name)
              parts.append(signal)
            elif isinstance(child, ast.Pointer):
              net_slice = ModuleReader.LoadPointer(module, child)
              parts.append(net_slice)
            elif isinstance(child, ast.Partselect):
              net_slice = ModuleReader.LoadPartselect(module, child)
              parts.append(net_slice)
            else:
              raise NotImplementedError(
                  f'not sure how to deal with {type(child)} in concat parts')

          # Important! Concatenations store parts in order of increasing bit
          # significance:
          concat = Concatenation(reversed(parts))
          connection.concat = concat

        instance.connections[port_name] = connection
      module.instances[instance.name] = instance

  def LoadParamList(module: Module, ast_node: ast.Node):
    if len(ast_node.children()):
        print('{} has a param list, which we ignore'.format(module))

