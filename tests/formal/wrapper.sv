module rvfi_wrapper (
	input         clock,
	input         reset,
	`RVFI_OUTPUTS
);

    // Convert from RVFI naming scheme to Amaranth interface naming scheme.
    `define RVFI_AMARANTH_PORT(suff) .rvfi__``suff(rvfi_``suff)
    `define RVFI_CSR_AMARANTH_PORTS(csr) \
        .rvfi__csr__``csr``__rmask(rvfi_csr_``csr``_rmask),       \
        .rvfi__csr__``csr``__wmask(rvfi_csr_``csr``_wmask),       \
        .rvfi__csr__``csr``__rdata(rvfi_csr_``csr``_rdata),       \
        .rvfi__csr__``csr``__wdata(rvfi_csr_``csr``_wdata)

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

                 `RVFI_AMARANTH_PORT(valid),
                 `RVFI_AMARANTH_PORT(order),
                 `RVFI_AMARANTH_PORT(insn),
                 `RVFI_AMARANTH_PORT(trap),
                 `RVFI_AMARANTH_PORT(halt),
                 `RVFI_AMARANTH_PORT(intr),
                 `RVFI_AMARANTH_PORT(mode),
                 `RVFI_AMARANTH_PORT(ixl),
                 `RVFI_AMARANTH_PORT(rs1_addr),
                 `RVFI_AMARANTH_PORT(rs2_addr),
                 `RVFI_AMARANTH_PORT(rs1_rdata),
                 `RVFI_AMARANTH_PORT(rs2_rdata),
                 `RVFI_AMARANTH_PORT(rd_addr),
                 `RVFI_AMARANTH_PORT(rd_wdata),
                 `RVFI_AMARANTH_PORT(pc_rdata),
                 `RVFI_AMARANTH_PORT(pc_wdata),
                 `RVFI_AMARANTH_PORT(mem_addr),
                 `RVFI_AMARANTH_PORT(mem_rmask),
                 `RVFI_AMARANTH_PORT(mem_wmask),
                 `RVFI_AMARANTH_PORT(mem_rdata),
                 `RVFI_AMARANTH_PORT(mem_wdata),

                 `RVFI_CSR_AMARANTH_PORTS(mscratch),
                 `RVFI_CSR_AMARANTH_PORTS(mcause),
                 `RVFI_CSR_AMARANTH_PORTS(mip),
                 `RVFI_CSR_AMARANTH_PORTS(mie),
                 `RVFI_CSR_AMARANTH_PORTS(mstatus)

`ifdef RO0_IN_RW_SPACE
                 `RVFI_CSR_AMARANTH_PORTS(misa)
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

    `ifdef RISCV_FORMAL_FAIRNESS
        // Prevent peripherals from hogging the bus with exorbitant wait states.
        // That way, if progress is never made, it's Sentinel's fault.
        `ifdef MEMIO_FAIRNESS
            assume (!timeout_bus[2]);
        `endif

        `ifndef NO_SHIFT_FAIRNESS
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
    `endif

    // Assume peripherals are well-behaved and take at least one cycle to
    // respond.
    if(~|timeout_bus && bus__cyc)
        assume(!bus__ack);

    // Nested traps not supported yet. Easy enough to lock the core into an
    // illegal insn and then repeatedly grab illegal insns.
    // TODO: Move into RISCV_FORMAL_FAIRNESS ifdef block?
    assume(trap_nest < 2);
end
endmodule
