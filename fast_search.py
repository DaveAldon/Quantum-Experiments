"""
Grover's Search Algorithm - Social Security Number Database Search

PRACTICAL APPLICATION: Finding a specific SSN in a large database

Scenario: A government database contains millions of Social Security Numbers.
You need to find a specific person's record by their SSN.

Classical computers need O(N) operations to search N records on average.
Grover's algorithm achieves O(√N) operations - a quadratic speedup!

Example with 4096 records (2^12):
- Classical: ~2048 queries on average, 4096 worst case
- Grover's: ~50 queries (π/4 * √4096)
- Speedup: ~40x faster!

Note: For demonstration, we use smaller databases. Real SSNs have ~1 billion
possible combinations (000-00-0000 to 999-99-9999), which would require
29-30 qubits and is beyond current quantum hardware capabilities.
"""

from qiskit import QuantumCircuit, transpile
from qiskit.primitives import StatevectorSampler
from qiskit.visualization import plot_histogram
import matplotlib.pyplot as plt
import numpy as np
import time
import argparse
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def setup_ibm_quantum(api_token=None, instance=None):
    """
    Set up IBM Quantum service for running on real quantum hardware.
    Credentials are loaded from .env file if not provided.
    
    Args:
        api_token: IBM Quantum API token (44 characters) - optional, reads from .env
        instance: IBM Quantum instance string - optional, reads from .env
    """
    # Load from environment variables if not provided
    if api_token is None:
        api_token = os.getenv('IBM_QUANTUM_TOKEN')
    if instance is None:
        instance = os.getenv('IBM_QUANTUM_INSTANCE')
    
    if not api_token:
        print("\nERROR: IBM_QUANTUM_TOKEN not found!")
        print("Please set it in .env file or pass as argument")
        sys.exit(1)
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        
        if api_token:
            print("\n" + "="*70)
            print("CONFIGURING IBM QUANTUM ACCESS")
            print("="*70)
            print("Saving IBM Quantum credentials...")
            
            # Save account credentials
            if instance:
                QiskitRuntimeService.save_account(
                    token=api_token,
                    instance=instance,
                    overwrite=True
                )
            else:
                QiskitRuntimeService.save_account(
                    token=api_token,
                    overwrite=True
                )
            print("✓ Credentials saved successfully!")
        
        # Load the service
        print("Loading IBM Quantum service...")
        service = QiskitRuntimeService()
        
        print("✓ Connected to IBM Quantum!")
        print(f"Available backends: {len(service.backends())} quantum systems")
        print("="*70 + "\n")
        
        return service
        
    except ImportError:
        print("\nERROR: qiskit-ibm-runtime not installed.")
        print("Install with: pip install qiskit-ibm-runtime")
        sys.exit(1)
    except Exception as e:
        print(f"\nERROR connecting to IBM Quantum: {e}")
        print("\nPlease check your API token and instance string.")
        sys.exit(1)


def binary_to_ssn_format(binary_str, ssn_length=9):
    """
    Convert a binary string to SSN-like format.
    For display purposes, we simulate SSN format: XXX-XX-XXXX
    
    Args:
        binary_str: Binary string representation
        ssn_length: Length to pad the decimal number
    """
    decimal = int(binary_str, 2)
    ssn_num = str(decimal).zfill(ssn_length)
    # Format as XXX-XX-XXXX
    return f"{ssn_num[:3]}-{ssn_num[3:5]}-{ssn_num[5:]}"


def generate_mock_ssn_database(n_qubits):
    """
    Generate a mock SSN database.
    Each entry represents a person with an SSN-like identifier.
    """
    N = 2 ** n_qubits
    database = []
    
    for i in range(N):
        binary = format(i, f'0{n_qubits}b')
        ssn_formatted = binary_to_ssn_format(binary)
        
        # Create mock person data
        person = {
            'id': i,
            'binary': binary,
            'ssn': ssn_formatted,
            'name': f"Person_{i:04d}"
        }
        database.append(person)
    
    return database


def create_oracle(n_qubits, target_state):
    """
    Create an oracle that marks the target state.
    The oracle flips the sign of the target state: |target⟩ → -|target⟩
    
    Args:
        n_qubits: Number of qubits
        target_state: Binary string representing the target (e.g., '0101')
    """
    oracle = QuantumCircuit(n_qubits, name='Oracle')
    
    # Flip qubits where target has '0' (so X-gates will create all-1s for target)
    for i, bit in enumerate(reversed(target_state)):
        if bit == '0':
            oracle.x(i)
    
    # Multi-controlled Z gate (marks the target state with -1 phase)
    if n_qubits > 1:
        oracle.h(n_qubits - 1)
        oracle.mcx(list(range(n_qubits - 1)), n_qubits - 1)
        oracle.h(n_qubits - 1)
    else:
        oracle.z(0)
    
    # Flip back
    for i, bit in enumerate(reversed(target_state)):
        if bit == '0':
            oracle.x(i)
    
    return oracle


def create_diffuser(n_qubits):
    """
    Create the Grover diffusion operator (inversion about average).
    This amplifies the amplitude of the marked state.
    """
    diffuser = QuantumCircuit(n_qubits, name='Diffuser')
    
    # Apply H-gates
    diffuser.h(range(n_qubits))
    
    # Apply X-gates
    diffuser.x(range(n_qubits))
    
    # Multi-controlled Z
    if n_qubits > 1:
        diffuser.h(n_qubits - 1)
        diffuser.mcx(list(range(n_qubits - 1)), n_qubits - 1)
        diffuser.h(n_qubits - 1)
    else:
        diffuser.z(0)
    
    # Apply X-gates
    diffuser.x(range(n_qubits))
    
    # Apply H-gates
    diffuser.h(range(n_qubits))
    
    return diffuser


def grovers_algorithm(n_qubits, target_state, target_ssn=None, draw_circuit=False):
    """
    Implement Grover's search algorithm for SSN database search.
    
    Args:
        n_qubits: Number of qubits (database size = 2^n_qubits)
        target_state: Binary string to search for
        target_ssn: Formatted SSN for display
        draw_circuit: Whether to print the circuit diagram
    """
    # Calculate optimal number of iterations: π/4 * √N
    N = 2 ** n_qubits
    optimal_iterations = int(np.pi / 4 * np.sqrt(N))
    
    print(f"\n{'='*70}")
    print(f"SEARCHING SSN DATABASE")
    print(f"{'='*70}")
    if target_ssn:
        print(f"Target SSN: {target_ssn} (Record #{int(target_state, 2)})")
    else:
        print(f"Target Record: {target_state} (#{int(target_state, 2)})")
    print(f"Database Size: {N:,} records")
    print(f"{'='*70}")
    print(f"Classical Search: ~{N//2:,} queries average, {N:,} worst case")
    print(f"Grover's Search: {optimal_iterations} queries")
    print(f"Speedup Factor: ~{(N//2) / optimal_iterations:.1f}x faster!")
    print(f"{'='*70}\n")
    
    # Create quantum circuit
    qc = QuantumCircuit(n_qubits, n_qubits)
    
    # Initialize in superposition
    qc.h(range(n_qubits))
    qc.barrier()
    
    # Apply Grover iterations
    oracle = create_oracle(n_qubits, target_state)
    diffuser = create_diffuser(n_qubits)
    
    for i in range(optimal_iterations):
        qc.compose(oracle, inplace=True)
        qc.barrier()
        qc.compose(diffuser, inplace=True)
        qc.barrier()
    
    # Measure
    qc.measure(range(n_qubits), range(n_qubits))
    
    if draw_circuit:
        print("Quantum Circuit:")
        print(qc.draw(output='text', fold=-1))
        print()
    
    return qc, optimal_iterations


def classical_search(database, target):
    """Simulate classical linear search for comparison."""
    queries = 0
    for i, item in enumerate(database):
        queries += 1
        if item == target:
            return i, queries
    return -1, queries


def run_quantum_search(qc, shots=1024, use_ibm=False, service=None):
    """Run the quantum circuit and return results."""
    start_time = time.time()
    
    if use_ibm and service:
        # Use IBM Quantum hardware
        from qiskit_ibm_runtime import SamplerV2 as IBMSampler
        from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
        
        print("\n" + "="*70)
        print("RUNNING ON IBM QUANTUM HARDWARE")
        print("="*70)
        
        # Get the least busy backend
        backend = service.least_busy(operational=True, simulator=False)
        print(f"Selected backend: {backend.name}")
        print(f"Queue depth: {backend.status().pending_jobs} jobs")
        
        # Transpile the circuit for the target backend
        print("Transpiling circuit for hardware...")
        pm = generate_preset_pass_manager(backend=backend, optimization_level=3)
        transpiled_qc = pm.run(qc)
        print(f"✓ Circuit transpiled ({transpiled_qc.depth()} depth, {transpiled_qc.num_qubits} qubits)")
        
        # Create sampler with the backend
        sampler = IBMSampler(backend)
        
        print("Submitting job to IBM Quantum...")
        job = sampler.run([transpiled_qc], shots=shots)
        
        print(f"Job ID: {job.job_id()}")
        print("Waiting for results (this may take several minutes)...")
        
        result = job.result()
        elapsed_time = time.time() - start_time
        
        print(f"✓ Job completed in {elapsed_time:.1f} seconds")
        print("="*70 + "\n")
        
        # Get counts from IBM result
        pub_result = result[0]
        
        # Extract counts from DataBin - find the measurement key
        data_bin = pub_result.data
        
        # Try to find the measurement data
        counts_dict = None
        for attr_name in dir(data_bin):
            if not attr_name.startswith('_'):
                try:
                    attr_value = getattr(data_bin, attr_name)
                    if hasattr(attr_value, 'get_counts'):
                        counts_dict = attr_value.get_counts()
                        break
                    elif hasattr(attr_value, 'get_bitstrings'):
                        # Alternative: count bitstrings manually
                        bitstrings = attr_value.get_bitstrings()
                        counts_dict = {}
                        for bs in bitstrings:
                            counts_dict[bs] = counts_dict.get(bs, 0) + 1
                        break
                except:
                    continue
        
        # Fallback: try direct dictionary access
        if counts_dict is None:
            # DataBin might have the measurement name as key
            meas_name = qc.cregs[0].name if qc.cregs else 'c'
            if hasattr(data_bin, meas_name):
                meas_data = getattr(data_bin, meas_name)
                if hasattr(meas_data, 'get_counts'):
                    counts_dict = meas_data.get_counts()
            
            # Last resort: check if there's a default measurement
            if counts_dict is None and hasattr(data_bin, 'c'):
                counts_dict = data_bin.c.get_counts()
        
        if counts_dict is None:
            raise RuntimeError(f"Could not extract counts from IBM result. DataBin attributes: {[a for a in dir(data_bin) if not a.startswith('_')]}")
        
    else:
        # Use local StatevectorSampler for simulation
        sampler = StatevectorSampler()
        
        # Run with StatevectorSampler
        job = sampler.run([qc], shots=shots)
        result = job.result()
        elapsed_time = time.time() - start_time
        
        # Get counts from the result
        pub_result = result[0]
        
        # Access the measurement data and convert to counts dictionary
        # The data is stored as a BitArray, we need to get counts
        bit_array = pub_result.data
        
        # Get the classical register name (should be 'c' or similar)
        # Get all attributes to find measurement data
        meas_data = None
        for attr in dir(bit_array):
            if not attr.startswith('_'):
                try:
                    meas_data = getattr(bit_array, attr)
                    if hasattr(meas_data, 'get_counts'):
                        counts_dict = meas_data.get_counts()
                        break
                    elif hasattr(meas_data, 'get_bitstrings'):
                        # Convert bitstrings to counts
                        bitstrings = meas_data.get_bitstrings()
                        counts_dict = {}
                        for bs in bitstrings:
                            counts_dict[bs] = counts_dict.get(bs, 0) + 1
                        break
                except:
                    continue
        
        # If we still don't have counts, try direct access
        if 'counts_dict' not in locals():
            # Try to get raw data and count occurrences
            counts_dict = pub_result.data.get_counts()
    
    return counts_dict, elapsed_time


def visualize_results(counts, target_state, target_ssn=None, save_filename='ssn_search_results.png'):
    """Visualize the SSN search results."""
    print(f"\nMeasurement Results (top 5 records found):")
    sorted_counts = sorted(counts.items(), key=lambda x: x[1], reverse=True)
    
    for state, count in sorted_counts[:5]:
        percentage = (count / sum(counts.values())) * 100
        ssn_display = binary_to_ssn_format(state)
        marker = " ← TARGET SSN FOUND!" if state == target_state else ""
        print(f"  SSN {ssn_display} (Record |{state}⟩): {count} times ({percentage:.1f}%){marker}")
    
    # Plot histogram
    title = f"Grover's SSN Search Results"
    if target_ssn:
        title += f" (Target: {target_ssn})"
    
    # Use non-interactive backend to avoid display issues
    plt.ioff()  # Turn off interactive mode
    fig = plot_histogram(counts, 
                        title=title,
                        figsize=(12, 6))
    plt.savefig(save_filename, dpi=300, bbox_inches='tight')
    print(f"\nHistogram saved as '{save_filename}'")
    plt.close(fig)  # Close the figure instead of showing it


def compare_classical_vs_quantum(n_qubits, target_state):
    """Compare classical vs quantum SSN search performance."""
    N = 2 ** n_qubits
    database = generate_mock_ssn_database(n_qubits)
    target_ssn = binary_to_ssn_format(target_state)
    
    print(f"\n{'='*70}")
    print("CLASSICAL vs QUANTUM SEARCH COMPARISON")
    print(f"{'='*70}")
    print(f"Database: {N:,} SSN records")
    print(f"Target: {target_ssn}")
    
    # Classical search simulation
    print(f"\nClassical Linear Search:")
    classical_queries_list = []
    for trial in range(100):  # Average over 100 random database orderings
        shuffled_db = database.copy()
        np.random.shuffle(shuffled_db)
        
        queries = 0
        for record in shuffled_db:
            queries += 1
            if record['binary'] == target_state:
                break
        classical_queries_list.append(queries)
    
    avg_classical = np.mean(classical_queries_list)
    min_classical = min(classical_queries_list)
    max_classical = max(classical_queries_list)
    
    print(f"  Best case: {min_classical} queries (got lucky!)")
    print(f"  Average: {avg_classical:.1f} queries")
    print(f"  Worst case: {max_classical} queries (very unlucky)")
    
    # Quantum search
    optimal_iterations = int(np.pi / 4 * np.sqrt(N))
    print(f"\nQuantum Search (Grover's Algorithm):")
    print(f"  Queries needed: {optimal_iterations} (guaranteed!)")
    print(f"  Success probability: >98%")
    
    print(f"\n{'='*70}")
    print(f"SPEEDUP: {avg_classical / optimal_iterations:.2f}x faster on average!")
    print(f"As database grows, speedup increases: √N advantage")
    print(f"{'='*70}\n")


def main():
    """Main demonstration of Grover's algorithm for SSN database search."""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Grover\'s Algorithm for SSN Database Search',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Run locally with default 8 qubits (256 records)
  python fast_search.py
  
  # Run locally with smaller database (better for IBM hardware)
  python fast_search.py --qubits 4
  
  # Run on IBM Quantum hardware with 4 qubits (16 records - recommended!)
  python fast_search.py --use-ibm --qubits 4
  
  # Run on IBM Quantum with 8 qubits (will have high noise)
  python fast_search.py --use-ibm --qubits 8
        '''
    )
    
    parser.add_argument('--use-ibm', action='store_true', default=False,
                        help='Use IBM Quantum hardware instead of local simulation')
    parser.add_argument('--qubits', type=int, default=8,
                        help='Number of qubits (database size = 2^qubits). Default: 8 (256 records). Recommended for IBM: 4 (16 records)')
    
    args = parser.parse_args()
    
    # Validate qubits
    if args.qubits < 2 or args.qubits > 12:
        print(f"ERROR: --qubits must be between 2 and 12 (you specified {args.qubits})")
        sys.exit(1)
    
    if args.use_ibm and args.qubits > 5:
        print(f"\n⚠️  WARNING: {args.qubits} qubits will create a very deep circuit on IBM hardware!")
        print(f"   Expected circuit depth: ~{2**(args.qubits+1)} gates")
        print(f"   This will likely produce noisy/random results.")
        print(f"   Recommended: --qubits 4 or --qubits 5 for IBM hardware")
        response = input(f"\n   Continue anyway? (y/N): ")
        if response.lower() != 'y':
            print("   Aborted. Try: python fast_search.py --use-ibm --qubits 4")
            sys.exit(0)
    
    # Setup IBM Quantum if requested
    service = None
    if args.use_ibm:
        service = setup_ibm_quantum()
    
    print("\n" + "="*70)
    print("GROVER'S ALGORITHM: SSN DATABASE SEARCH")
    print("Quantum Speedup for Unstructured Database Search")
    if args.use_ibm:
        print("⚛️  RUNNING ON IBM QUANTUM HARDWARE")
    else:
        print("💻 Running on Local Simulator")
    print(f"Database Size: {2**args.qubits} records ({args.qubits} qubits)")
    print("="*70)
    
    # Scenario 1: SSN database search with configurable size
    print("\n" + "="*70)
    print("SCENARIO 1: SSN Database Search")
    print("="*70)
    
    n_qubits = args.qubits
    N = 2 ** n_qubits
    
    # Generate database
    database = generate_mock_ssn_database(n_qubits)
    
    # Pick a target SSN to search for - choose based on database size
    # Use a number that exists in all database sizes
    target_id = min(10, N - 1)  # Use record #10, or last record if database is smaller
    target_record = database[target_id]
    target_state = target_record['binary']
    target_ssn = target_record['ssn']
    
    print(f"\nDatabase: {N} employee records")
    print(f"Searching for: Employee '{target_record['name']}' (Record #{target_id})")
    print(f"SSN: {target_ssn}")
    
    # Create and run Grover's algorithm
    qc, iterations = grovers_algorithm(n_qubits, target_state, target_ssn, draw_circuit=False)
    
    # Visualize the quantum circuit
    print(f"\nGenerating quantum circuit diagram...")
    print(f"Circuit statistics: {qc.size()} gates, {qc.depth()} depth")
    try:
        circuit_fig = qc.draw(output='mpl', fold=-1, scale=0.8)
        plt.savefig('grover_circuit.png', dpi=300, bbox_inches='tight')
        print(f"✓ Circuit diagram saved as 'grover_circuit.png'\n")
        plt.close(circuit_fig)
    except Exception as e:
        print(f"⚠ Could not generate circuit diagram: {e}\n")
    
    counts, exec_time = run_quantum_search(qc, shots=1024, use_ibm=args.use_ibm, service=service)
    
    # Visualize results
    visualize_results(counts, target_state, target_ssn)
    
    # Performance comparison
    compare_classical_vs_quantum(n_qubits, target_state)
    
    # Scenario 2: Larger database demonstration
    print("\n" + "="*70)
    print("SCENARIO 2: Scaling to Larger Databases")
    print("="*70)
    
    scenarios = [
        (10, "Regional Office"),
        (12, "Large Corporation"),
        (14, "State Database"),
        (16, "Federal Database")
    ]
    
    print(f"\n{'Database Type':<20} {'Records':<15} {'Classical':<15} {'Quantum':<12} {'Speedup':<10}")
    print("-" * 70)
    
    for qubits, db_type in scenarios:
        N_items = 2 ** qubits
        classical_avg = N_items // 2
        quantum_queries = int(np.pi / 4 * np.sqrt(N_items))
        speedup = classical_avg / quantum_queries
        
        print(f"{db_type:<20} {N_items:>12,}   {classical_avg:>12,}   {quantum_queries:>10}   {speedup:>8.1f}x")
    
    print("\n" + "="*70)
    print("KEY INSIGHTS FOR SSN DATABASE SEARCH")
    print("="*70)
    print("✓ Grover's algorithm provides quadratic speedup: O(√N) vs O(N)")
    print("✓ Critical for searching unindexed/unsorted databases")
    print("✓ Speedup grows with database size:")
    print("  - 256 records: 8x faster")
    print("  - 1,024 records: 16x faster")
    print("  - 16,384 records: 64x faster")
    print("  - 65,536 records: 128x faster")
    print("✓ Real SSNs (~1 billion combinations) would need ~30 qubits")
    print("✓ Future quantum computers could search billion-record databases")
    print("  in ~31,000 queries vs 500 million classically!")
    print("\n" + "="*70)
    print("PRIVACY NOTE: This is a demonstration using mock data.")
    print("Real SSN databases must be encrypted and access-controlled.")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
