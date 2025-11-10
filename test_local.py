"""Quick test of the local simulation before using IBM API credits"""
import sys
sys.path.insert(0, '/Users/dcrawford/Documents/Github-Projects/Quantum-Experiments')

from fast_search import grovers_algorithm, run_quantum_search, visualize_results, binary_to_ssn_format

print("Testing local simulation...")

# Small test: 4 qubits = 16 items
n_qubits = 4
target_state = '1010'
target_ssn = binary_to_ssn_format(target_state)

print(f"Creating circuit for target: {target_ssn}")
qc, iterations = grovers_algorithm(n_qubits, target_state, target_ssn, draw_circuit=False)

print("Running simulation...")
counts, exec_time = run_quantum_search(qc, shots=100, use_ibm=False, service=None)

print(f"\nResults in {exec_time:.2f}s:")
for state, count in sorted(counts.items(), key=lambda x: x[1], reverse=True)[:3]:
    print(f"  {state}: {count}")

if target_state in counts:
    print(f"\n✓ SUCCESS: Target {target_state} found with {counts[target_state]} counts")
else:
    print(f"\n✗ PROBLEM: Target {target_state} not in results")
    
print("\nLocal test complete. Safe to try --use-ibm")
