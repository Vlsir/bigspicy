module testmodule (
    in,
    out
);
    input in;
    output out;

    assign out = in;

    reg x;
    reg y;
    wire z;
    assign z = {x, y};

endmodule
