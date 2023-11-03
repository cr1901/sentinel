module rvfi_wrapper (
	input         clock,
	input         reset,
	`RVFI_OUTPUTS
);
	(* keep *) `rvformal_rand_reg bus__ack;
	(* keep *) `rvformal_rand_reg [31:0] bus__dat_r;

	(* keep *) wire        bus__cyc;
    (* keep *) wire        bus__stb;
    (* keep *) wire [3:0]  bus__sel;
    (* keep *) wire        bus__we;
	(* keep *) wire [29:0] bus__adr;
	(* keep *) wire [31:0] bus__dat_w;

    sentinel uut(
                 .clk(clock),
                 .rst(reset),
        
                 .bus__adr (bus__adr),
                 .bus__cyc (bus__cyc),
                 .bus__dat_r (bus__dat_r),
                 .bus__dat_w (bus__dat_w),
                 .bus__sel (bus__sel),
                 .bus__stb (bus__stb),
                 .bus__we (bus__we),
                 .bus__ack (bus__ack),

                 .rvfi__valid     (rvfi_valid    ),
                 .rvfi__order     (rvfi_order    ),
                 .rvfi__insn      (rvfi_insn     ),
                 .rvfi__trap      (rvfi_trap     ),
                 .rvfi__halt      (rvfi_halt     ),
                 .rvfi__intr      (rvfi_intr     ),
                 .rvfi__mode      (rvfi_mode     ),
                 .rvfi__ixl       (rvfi_ixl      ),
                 .rvfi__rs1_addr  (rvfi_rs1_addr ),
                 .rvfi__rs2_addr  (rvfi_rs2_addr ),
                 .rvfi__rs1_rdata (rvfi_rs1_rdata),
                 .rvfi__rs2_rdata (rvfi_rs2_rdata),
                 .rvfi__rd_addr   (rvfi_rd_addr  ),
                 .rvfi__rd_wdata  (rvfi_rd_wdata ),
                 .rvfi__pc_rdata  (rvfi_pc_rdata ),
                 .rvfi__pc_wdata  (rvfi_pc_wdata ),
                 .rvfi__mem_addr  (rvfi_mem_addr ),
                 .rvfi__mem_rmask (rvfi_mem_rmask),
                 .rvfi__mem_wmask (rvfi_mem_wmask),
                 .rvfi__mem_rdata (rvfi_mem_rdata),
                 .rvfi__mem_wdata (rvfi_mem_wdata)
    );

reg [3:0] timeout_bus = 0;

always @(posedge clock) begin
    timeout_bus <= 0;

    if (bus__cyc && !bus__ack)
        timeout_bus <= timeout_bus + 1;

    // Prevent peripherals from hogging the bus with exorbitant wait states.
    // That way, if progress is never made, it's Sentinel's fault.
    `ifdef MEMIO_FAIRNESS
        assume (!timeout_bus[3]);
    `endif

    // Assume peripherals are well-behaved and take at least one cycle to
    // respond.
    if(~|timeout_bus && bus__cyc)
        assume(!bus__ack);
end

`ifdef NO_SHIFT_FAIRNESS
// Do nothing
`else
// Constrain shift ops to either shift 0 or 1.
always @(posedge clock) begin
    // Was for testing; generates interesting CEX w/ nested exceptions.
    // if((rvfi_insn[0:6] == 7'b0010011) &&
    //    (rvfi_insn[12:14] == 3'b001)) begin
    //     assert (rvfi_insn[20:24] < 2);
    // end

    if((rvfi_insn[0:6] == 7'b0010011) &&
       (rvfi_insn[12:14] == 3'b001)) begin
        assume (rvfi_insn[20:24] < 2);
    end

    if((rvfi_insn[0:6] == 7'b0010011) &&
       (rvfi_insn[12:14] == 3'b101)) begin
        assume (rvfi_insn[20:24] < 2);
    end
end
`endif
endmodule
