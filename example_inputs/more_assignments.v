module simple_assignment (
  input in,
  input [3:0] in_bus,
  output out_0,
  output out_1,
  output [1:0] out_bus_0,
  output [1:0] out_bus_1,
  output [3:0] out_bus_2
);
  // pyverilog: left and right are ast.Identifier.
  assign out_0 = in;
  // pyverilog: left and right are ast.Pointer.
  assign out_bus_0[0] = in_bus[3];
  // pyverilog: left is ast.Identifier, right is ast.Partselect.
  assign out_bus_1 = in_bus[2:1];
  // pyverilog: left is ast.Identifier, right is ast.Concat.
  assign out_bus_2 = {in_bus[2:1], in_bus[3], in_bus[0]};
  // pyverilog: left is ast.LConcat, right is ast.Partselect.
  assign {out_bus_0[0], out_1} = in_bus[1:0];
  // pyverilog: left and right are ast.Partselect.
  assign out_bus_2[3:1] = in_bus[1:0];
endmodule
