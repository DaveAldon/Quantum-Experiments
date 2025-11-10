"""
Pre-flight check before using IBM Quantum API credits
"""
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("="*70)
print("PRE-FLIGHT CHECK")
print("="*70)

issues = []

# Check 1: Import all required modules
print("\n1. Checking imports...")
try:
    from qiskit import QuantumCircuit
    from qiskit.primitives import StatevectorSampler
    from qiskit.visualization import plot_histogram
    from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2
    from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
    print("   ✓ All imports successful")
except ImportError as e:
    print(f"   ✗ Import error: {e}")
    issues.append(f"Missing import: {e}")

# Check 2: Create a simple circuit
print("\n2. Creating test circuit...")
try:
    qc = QuantumCircuit(2, 2)
    qc.h(0)
    qc.cx(0, 1)
    qc.measure([0, 1], [0, 1])
    print(f"   ✓ Circuit created: {qc.num_qubits} qubits, {qc.num_clbits} clbits")
except Exception as e:
    print(f"   ✗ Circuit creation error: {e}")
    issues.append(f"Circuit error: {e}")

# Check 3: Test local simulation
print("\n3. Testing local simulation...")
try:
    sampler = StatevectorSampler()
    job = sampler.run([qc], shots=10)
    result = job.result()
    pub_result = result[0]
    
    # Try to extract counts
    data_bin = pub_result.data
    found_counts = False
    
    for attr_name in dir(data_bin):
        if not attr_name.startswith('_'):
            try:
                attr_value = getattr(data_bin, attr_name)
                if hasattr(attr_value, 'get_counts'):
                    counts = attr_value.get_counts()
                    print(f"   ✓ Local simulation works! Found counts via '{attr_name}': {counts}")
                    found_counts = True
                    break
            except:
                pass
    
    if not found_counts:
        print(f"   ✗ Could not extract counts. DataBin attrs: {[a for a in dir(data_bin) if not a.startswith('_')]}")
        issues.append("Cannot extract counts from local simulation")
        
except Exception as e:
    print(f"   ✗ Local simulation error: {e}")
    issues.append(f"Simulation error: {e}")

# Check 4: IBM credentials (don't actually connect, just check format)
print("\n4. Checking IBM credentials...")
token = os.getenv('IBM_QUANTUM_TOKEN')
instance = os.getenv('IBM_QUANTUM_INSTANCE')

if not token:
    print(f"   ✗ IBM_QUANTUM_TOKEN not found in .env file")
    issues.append("Missing IBM_QUANTUM_TOKEN in .env")
elif len(token) == 44:
    print(f"   ✓ Token loaded from .env ({len(token)} characters)")
else:
    print(f"   ⚠ Token length is {len(token)}, expected 44")
    
if not instance:
    print(f"   ⚠ IBM_QUANTUM_INSTANCE not found in .env file (optional)")
elif instance.startswith("crn:v1:bluemix"):
    print(f"   ✓ Instance loaded from .env")
else:
    print(f"   ⚠ Instance format may be incorrect")

print("\n" + "="*70)
if issues:
    print("ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    print("\n⚠️  FIX THESE BEFORE USING --use-ibm")
else:
    print("✓ ALL CHECKS PASSED")
    print("✓ Safe to run: python fast_search.py --use-ibm")
print("="*70)
