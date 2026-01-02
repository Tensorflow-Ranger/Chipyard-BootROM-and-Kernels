section .text.start
.globl _start
.option norvc

# Constants
.equ SSTATUS_SPP,  1 << 8  # Supervisor Previous Privilege bit
.equ SSTATUS_SPIE, 1 << 5  # Supervisor Previous Interrupt Enable

_start:
    # 1. Install S-mode trap handler
    la   t0, context_switch
    csrw stvec, t0

    # 2. Initialize task0 context pointer in sscratch
    la   t0, task0_ctx
    csrw sscratch, t0

    # 3. Fabricate task1 initial context
    # We populate the saved context so when we switch TO task1,
    # it looks like it just 'paused' there.
    la   t0, task1_stack_top
    la   t1, task1_ctx
    sd   t0, 0(t1)        # sp
    la   t0, task1
    sd   t0, 24(t1)       # sepc (entry point)

    # 4. Enter Task 0 in U-MODE
    # We cannot use 'j task0'. We must use 'sret' to drop privilege.
    
    # Set exception program counter to task0
    la   t0, task0
    csrw sepc, t0

    # Setup sstatus:
    # Clear SPP (Bit 8) -> 0 means "Previous mode was User"
    # Set SPIE (Bit 5)  -> 1 means "Enable interrupts after sret"
    li   t0, SSTATUS_SPP
    csrc sstatus, t0      # Clear SPP for U-mode
    li   t0, SSTATUS_SPIE
    csrs sstatus, t0      # Set SPIE

    # Jump to User Mode
    sret

# -------------------------
# User Mode Tasks
# -------------------------
task0:
    li t0, 0
loop0:
    addi t0, t0, 1
    # This ecall will trap to S-Mode (cause 8)
    ecall
    j loop0

task1:
    li t0, 100
loop1:
    addi t0, t0, -1
    ecall
    j loop1

# -------------------------
# Trap Handler
# -------------------------
.section .text.context_switch
.globl context_switch
.align 2
context_switch:
    # 1. Check cause
    csrr t0, scause
    li   t1, 8                  # 8 = ECALL from U-mode
    bne  t0, t1, s_trap_vector

    # 2. Perform Switch
    call save_context
    call switch_context
    j restore_context


# -------------------------
# Save Context
# -------------------------
.section .text.save_context
.globl save_context
save_context:
    # We need to save registers into the structure pointed to by sscratch.
    # But we also need a temporary register to do address calculation.
    # We swap t0 with sscratch.
    # Now: t0 = &current_ctx, sscratch = original_t0_value
    csrrw t0, sscratch, t0
    
    sd   sp,  0(t0)
    sd   ra,  8(t0)
    sd   s0, 16(t0)
    
    # Retrieve the original t0 from sscratch and save it to context
    csrr t1, sscratch
    sd   t1, 32(t0) # Assuming we extended space for T0

    # CRITICAL FOR ECALL: 
    # The SEPC currently points TO the ecall instruction.
    # We must save SEPC + 4 so we resume AFTER the ecall.
    csrr t1, sepc
    addi t1, t1, 4
    sd   t1, 24(t0)

    # Restore t0 so the handler logic can use it (it points to ctx)
    mv   t0, t0 
    ret
# -------------------------
# Switch Context Pointer
# -------------------------
.section .text.switch_context
.globl switch_context
switch_context:
    # t0 currently holds address of current ctx (from save_context logic)
    # But let's reload from sscratch just to be safe and clean
    csrr t0, sscratch 

    la   t1, task0_ctx
    la   t2, task1_ctx

    beq  t0, t1, switch_to_1

switch_to_0:
    csrw sscratch, t1  # sscratch points to Task 0
    ret

switch_to_1:
    csrw sscratch, t2  # sscratch points to Task 1
    ret

# -------------------------
# Restore Context
# -------------------------
.section .text.restore_context
.globl restore_context
restore_context:
    csrr t0, sscratch   # Get pointer to the NEXT task's context

    ld   sp,  0(t0)
    ld   ra,  8(t0)
    ld   s0, 16(t0)
    ld   t1, 24(t0)     # Load saved PC
    
    csrw sepc, t1       # Set where sret will jump to
    
    # Restore the general purpose temp reg we saved
    ld   t0, 32(t0) 

    sret

# -------------------------
# Trap Vector (Catch-all)
# -------------------------
.section .text.trap
.globl s_trap_vector
s_trap_vector:
    # Infinite loop for unhandled traps
    j s_trap_vector

# -------------------------
# Data
# -------------------------
.section .bss
.align 8

# Contexts (Increased size to store T0)
task0_ctx: .space 64
task1_ctx: .space 64

# Stacks
.align 12
task0_stack:
    .space 4096
task0_stack_top:

.align 12
task1_stack:
    .space 4096
task1_stack_top:
