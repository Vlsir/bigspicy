module dummy (
  input [3:0] in
);
endmodule

module concatenation (
  input in,
  input [3:0] in_bus,
  output out_0,
  output out_1,
  output [1:0] out_bus_0,
  output [1:0] out_bus_1,
  output [3:0] out_bus_2
);

dummy dummy_0 (
  .in({in_bus[2:1], in_bus[3], in})
);

endmodule
