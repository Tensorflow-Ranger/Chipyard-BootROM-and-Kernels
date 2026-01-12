.section .text.start
.globl _start
.option norvc

# -------------------------
# Constants
# -------------------------
.equ SSTATUS_SPP,   1 << 8
.equ SSTATUS_SPIE,  1 << 5
.equ SSTATUS_SUM,   1 << 18   

# Page Table Constants
.equ PTE_V, 1 << 0
.equ PTE_R, 1 << 1
.equ PTE_W, 1 << 2
.equ PTE_X, 1 << 3
.equ PTE_U, 1 << 4
.equ PTE_G, 1 << 5
.equ PTE_A, 1 << 6
.equ PTE_D, 1 << 7

# SATP Constants
.equ SATP_MODE_SV39, 8

_start:
    # -------------------------
    # 1. Setup Page Tables (SV39)
    # -------------------------
    la   t0, root_page_table   
    
    # Physical Base: 0x80000000 -> PPN = 0x80000
    li   t1, 0x80000          
    slli t1, t1, 10           
    
    # Entry A: Kernel Mapping (VA 0x80000000 -> PA 0x80000000, U=0)
    li   t2, (PTE_V | PTE_R | PTE_W | PTE_X | PTE_A | PTE_D | PTE_G)
    or   t3, t1, t2           
    li   t4, 16               # Index 2 (0x80... >> 30 = 2), 2 * 8 = 16 bytes
    add  t4, t0, t4
    sd   t3, 0(t4)

    # Entry B: User Mapping (VA 0x00000000 -> PA 0x80000000, U=1)
    li   t2, (PTE_V | PTE_R | PTE_W | PTE_X | PTE_A | PTE_D | PTE_U)
    or   t3, t1, t2
    sd   t3, 0(t0)            # Index 0

    # -------------------------
    # 2. Enable Paging
    # -------------------------
    srli t1, t0, 12           
    li   t2, SATP_MODE_SV39
    slli t2, t2, 60
    or   t1, t1, t2
    csrw satp, t1
    sfence.vma zero, zero     

    # -------------------------
    # 3. Initialization
    # -------------------------
    la   t0, context_switch
    csrw stvec, t0

    la   t0, task0_ctx
    csrw sscratch, t0

    # Fabricate Task 1 Context (Aliased to 0x0...)
    la   t0, task1_stack_top
    la   t1, task1_ctx
    la   t2, task1
    
    li   t3, 0x80000000
    sub  t0, t0, t3       # Virtual SP
    sub  t2, t2, t3       # Virtual PC
    
    sd   t0, 0(t1)        
    sd   t2, 24(t1)       

    # -------------------------
    # 4. Enter Task 0
    # -------------------------
    la   t0, task0
    sub  t0, t0, t3       # Virtual PC Task 0
    csrw sepc, t0

    li   t0, SSTATUS_SPP
    csrc sstatus, t0      
    li   t0, SSTATUS_SPIE
    csrs sstatus, t0      
    sret

# -------------------------
# User Mode Tasks (VA 0x0...)
# -------------------------
task0:
    li t0, 0
loop0:
    addi t0, t0, 1
    ecall
    j loop0

task1:
    li t1, 100
loop1:
    addi t1, t1, -1
    ecall
    j loop1

# -------------------------
# Trap Handler (VA 0x80...)
# -------------------------
.section .text.context_switch
.globl context_switch
.align 2
context_switch:
    csrr t0, scause
    li   t1, 8                  
    bne  t0, t1, s_trap_vector
    call save_context
    call switch_context
    j restore_context

.section .text.save_context
.globl save_context
save_context:
    csrrw t0, sscratch, t0
    sd   sp,  0(t0)
    sd   ra,  8(t0)
    sd   s0, 16(t0)
    csrr t1, sscratch
    sd   t1, 32(t0) 
    csrr t1, sepc
    addi t1, t1, 4
    sd   t1, 24(t0)
    csrw sscratch, t0 # The previous fix
    ret

.section .text.switch_context
.globl switch_context
switch_context:
    csrr t0, sscratch 
    la   t1, task0_ctx
    la   t2, task1_ctx
    beq  t0, t1, switch_to_1
switch_to_0:
    csrw sscratch, t1
    ret
switch_to_1:
    csrw sscratch, t2
    ret

.section .text.restore_context
.globl restore_context
restore_context:
    csrr t0, sscratch
    ld   sp,  0(t0)     
    ld   ra,  8(t0)
    ld   s0, 16(t0)
    ld   t1, 24(t0)     
    csrw sepc, t1
    ld   t0, 32(t0) 
    sret

.section .text.trap
s_trap_vector:
    j s_trap_vector

# -------------------------
# Data
# -------------------------
.section .bss
.align 12
root_page_table:
    .space 4096

.section .data
.align 8
task0_ctx: .space 64
task1_ctx: .space 64

.section .stack
.align 12
task0_stack:
    .space 4096
task0_stack_top:

.align 12
task1_stack:
    .space 4096
task1_stack_top: