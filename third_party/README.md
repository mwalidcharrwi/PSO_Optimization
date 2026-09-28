# Third-party baselines

`guoq_preserve_coupling.patch` applies to [qqq-wisc/guoq](https://github.com/qqq-wisc/guoq)
at the commit in `GUOQ_COMMIT`.  It makes two changes, used for the comparison on
already-mapped circuits (`qcpso/bench/literature.py`):

* `resynth.py --port P` and `GUOQ_RESYNTH_PORT` (Java client), so that several
  GUOQ instances can run in parallel;
* `resynth.py --preserve_coupling`: each block sent to BQSKit is synthesised with
  a `MachineModel` whose coupling graph contains only the qubit pairs already
  coupled in that block.  Together with GUOQ's own `--preserve-mapping` (rule
  filtering), the output then respects the device mapping.  Without it,
  GUOQ's resynthesis may create CNOTs between uncoupled qubits.

Setup:

```bash
git clone https://github.com/qqq-wisc/guoq.git && cd guoq
git checkout $(cat ../third_party/GUOQ_COMMIT)
git apply ../third_party/guoq_preserve_coupling.patch
mvn package -Dmaven.test.skip
pip install bqskit
export GUOQ_DIR=$PWD
```
