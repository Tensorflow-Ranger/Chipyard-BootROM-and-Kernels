.option norvc
.section .text.start
.globl _start
_start:
    # Open PMP: allow S-mode RWX everywhere
    li  t0, -1
    csrw pmpaddr0, t0
    li  t0, 0x0F
    csrw pmpcfg0, t0

    # Set MPP = S-mode
    csrr t0, mstatus
    li   t1, ~(3 << 11)
    and  t0, t0, t1
    li   t1, (1 << 11)
    or   t0, t0, t1
    csrw mstatus, t0

    # Set kernel entry
    li   t0, 0x80000000
    csrw mepc, t0

    mret