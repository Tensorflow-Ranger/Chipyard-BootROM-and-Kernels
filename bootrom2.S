    .option norvc
    .section .text.init
    .globl _start
_start:
    # ------------------------
    # 1. Set up M-mode stack
    # ------------------------
    la      sp, boot_stack_top

    # ------------------------
    # 2. (Optional) build a trivial Sv39 1:1 map
    #    Map VA 0..1GiB -> PA 0..1GiB using a single L2 huge page PTE.
    # ------------------------
    la      t0, root_page_table        # t0 = root PT base
    li      t1, 0
    sd      t1, 0(t0)                  # clear first entry

    # For Sv39, an L2 PTE at index 0 covers 0..1GiB if we mark it as leaf.
    # PPN = 0 (maps PA 0), flags = V | R | W | X | G | A | D
    li      t1, (1 << 0) | (1 << 1) | (1 << 2) | (1 << 3) | (1 << 5) | (1 << 6)
    #       V=bit0, R=1, W=2, X=3, A=6, D=7 (check your exact flag bits against the spec)
    sd      t1, 0(t0)                  # PTE[0] = PA(0) + flags

    # satp = MODE=Sv39 (8) | ASID=0 | PPN=(root_pt >> 12)
    la      t0, root_page_table
    srl     t0, t0, 12                 # PPN
    li      t1, (8 << 60)              # MODE=8 (Sv39) in top 4 bits
    or      t0, t0, t1
    csrw    satp, t0
    sfence.vma x0, x0                  # flush TLB

    # If you prefer Linux to start with paging OFF, comment out satp/sfence above
    # and instead: csrw satp, x0

    # ------------------------
    # 3. Open PMP (allow S-mode full access)
    # ------------------------
    li      t0, 0
    csrw    pmpcfg0, t0                # clear PMP (implementation-defined)
    csrw    pmpaddr0, t0               # allow full access or configure as needed

    # ------------------------
    # 4. Delegate traps/interrupts to S-mode
    # ------------------------
    # Synchronous exceptions: delegate almost everything to S-mode
    li      t0, 0
    # Example: delegate all low 16 exception codes (adjust for your needs)
    li      t0, 0xFFFF
    csrw    medeleg, t0

    # Interrupt delegation: S-mode software, timer, external
    li      t0, (1 << 1)       # SSIP
    ori     t0, t0, (1 << 5)   # STIP
    ori     t0, t0, (1 << 9)   # SEIP
    csrw    mideleg, t0
    # ------------------------
    # 5. Allow S-mode access to counters
    # ------------------------
    li      t0, 0x7            # CY, TM, INSTRET
    csrw    mcounteren, t0
    csrw    scounteren, t0

    # ------------------------
    # 6. Set S-mode trap vector (Linux will overwrite)
    # ------------------------
    la      t0, s_trap_vector
    csrw    stvec, t0

    # ------------------------
    # 7. Prepare registers for Linux entry
    # ------------------------
    # a0 = hartid, a1 = dtb_phys_addr
    csrr    a0, mhartid
    la      a1, _dtb           # or li a1, DTB_PHYS_ADDR if linked elsewhere

    # ------------------------
    # 8. Drop from M-mode to S-mode and jump to kernel
    # ------------------------
    # Set mstatus.MPP = S-mode (01)
    csrr    t0, mstatus
    li      t1, (3 << 11)      # mask for MPP (bits 12:11)
    not     t1, t1
    and     t0, t0, t1         # clear MPP
    li      t1, (1 << 11)      # MPP=01 (S-mode)
    or      t0, t0, t1
    csrw    mstatus, t0

    # mepc = kernel_entry (physical address)
    la      t0, kernel_entry
    csrw    mepc, t0

    li   t0, 1 << 12          # 1
    csrs medeleg, t0          # 2
    li   t0, 0x10100          # 3
    li   t1, 0xef             # 4
    sd   t1, 0(t0)            # 5
    srli t0, t0, 12           # 6
    li   t1, 8 << 60          # 7
    or   t0, t0, t1           # 8
    csrw satp, t0             # 9
    sfence.vma x0, x0         # 10
    mret                        # -> S-mode, PC = kernel_entry

    # ------------------------
    # Dummy S-mode trap handler (for bare-metal / debugging)
    # Linux will install its own early on.
    # ------------------------
s_trap_vector:
    j       s_trap_vector      # spin on unexpected traps

    .section .bss
    .align 12                  # 4 KiB aligned
root_page_table:
    .space 4096                # one page for root PT

    .align 12
boot_stack:
    .space 4096
boot_stack_top:
