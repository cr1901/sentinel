module rvfi_wrapper (
	input         clock,
	input         reset,
	`RVFI_OUTPUTS
);
	(* keep *) `rvformal_rand_reg bus__ack;
    (* keep *) `rvformal_rand_reg irq;
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

                 .irq (irq),

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
                 .rvfi__mem_wdata (rvfi_mem_wdata),

                 .rvfi__csr__mscratch__rmask(rvfi_csr_mscratch_rmask),
                 .rvfi__csr__mscratch__wmask(rvfi_csr_mscratch_wmask),
                 .rvfi__csr__mscratch__rdata(rvfi_csr_mscratch_rdata),
                 .rvfi__csr__mscratch__wdata(rvfi_csr_mscratch_wdata),

                 .rvfi__csr__mcause__rmask(rvfi_csr_mcause_rmask),
                 .rvfi__csr__mcause__wmask(rvfi_csr_mcause_wmask),
                 .rvfi__csr__mcause__rdata(rvfi_csr_mcause_rdata),
                 .rvfi__csr__mcause__wdata(rvfi_csr_mcause_wdata),

`ifdef RO0_IN_RW_SPACE
                 .rvfi__csr__misa__rmask(rvfi_csr_misa_rmask),
                 .rvfi__csr__misa__wmask(rvfi_csr_misa_wmask),
                 .rvfi__csr__misa__rdata(rvfi_csr_misa_rdata),
                 .rvfi__csr__misa__wdata(rvfi_csr_misa_wdata)
`endif
    );

reg [2:0] timeout_bus = 0;
reg [1:0] trap_nest = 0;

always @(posedge clock) begin
    timeout_bus <= 0;

    if (bus__cyc && !bus__ack)
        timeout_bus <= timeout_bus + 1;

    if (rvfi_trap && bus__ack) begin
        trap_nest <= trap_nest + 2'b01;

        // If mret and in trap, decrement nesting cntr.
        if((rvfi_insn == 32'b00110000001000000000000001110011) &&
            |trap_nest) begin
            trap_nest <= trap_nest - 2'b01;
        end
    end

    // Prevent peripherals from hogging the bus with exorbitant wait states.
    // That way, if progress is never made, it's Sentinel's fault.
    `ifdef MEMIO_FAIRNESS
        assume (!timeout_bus[2]);
    `endif


    `ifdef NO_SHIFT_FAIRNESS
    // Do nothing
    `else
        // Constrain shift ops to either shift 0 or 1.
        // Was for testing; generates interesting CEX w/ nested exceptions.
        // if((rvfi_insn[0:6] == 7'b0010011) &&
        //    (rvfi_insn[12:14] == 3'b001)) begin
        //     assert (rvfi_insn[20:24] < 2);
        // end

        // SLLI
        if((rvfi_insn[0:6] == 7'b0010011) &&
           (rvfi_insn[12:14] == 3'b001)) begin
            assume (rvfi_insn[20:24] < 2);
        end

        // SR*I
        if((rvfi_insn[0:6] == 7'b0010011) &&
           (rvfi_insn[12:14] == 3'b101)) begin
            assume (rvfi_insn[20:24] < 2);
        end

        // SR*
        if((rvfi_insn[0:6] == 7'b0110011) &&
           (rvfi_insn[12:14] == 3'b101)) begin
            assume (rvfi_rs2_rdata < 2);
        end

        // SLL
        if((rvfi_insn[0:6] == 7'b0110011) &&
           (rvfi_insn[12:14] == 3'b001)) begin
            assume (rvfi_rs2_rdata < 2);
        end
    `endif

    // Assume peripherals are well-behaved and take at least one cycle to
    // respond.
    if(~|timeout_bus && bus__cyc)
        assume(!bus__ack);

    // Nested traps not supported yet. Easy enough to lock the core into an
    // illegal insn and then repeatedly grab illegal insns.
    assume(trap_nest < 2);
end
endmodule
