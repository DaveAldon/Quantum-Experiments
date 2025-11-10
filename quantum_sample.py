from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler
 
qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()
 
sampler = StatevectorSampler()
result = sampler.run([qc], shots=1024).result()
print(result[0].data.meas.get_counts())

from qiskit.visualization import plot_histogram
 
counts = result[0].data.meas.get_counts()
plot_histogram(counts)
 
# Include the next line if you are not using Python in a Jupyter notebook
# plt.show()