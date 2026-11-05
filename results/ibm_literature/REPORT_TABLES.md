### Two-qubit (ECR) gate count

| circuit | input | TKET (conn.-preserving) | QUESO (15 min) | GUOQ 1 min | GUOQ 5 min | GUOQ 15 min | HyPSO-QCO v1 | v2 w/o swarm | v2, 1 worker | **HyPSO-QCO v2 (15 min)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 311 | 299 | 311 | 275 | 231 | 199 | 309 | 156 | 164 | **153** |
| heisenberg_8 | 420 | 420 | 420 | 417 | 366 | 326 | 420 | **266** | 283 | 276 |
| add_17 | 499 | 495 | 499 | 473 | 440 | 421 | 491 | **389** | 407 | 390 |
| qae_17 | 541 | 537 | 541 | 505 | 446 | 428 | 527 | **413** | 427 | 420 |
| qft_16 | 614 | 610 | 614 | 604 | 551 | 536 | 604 | **519** | 541 | **519** |
| hubbard_8 | 1,344 | 1,251 | 1,336 | 1,328 | 1,252 | 1,165 | 1,334 | **915** | 968 | 930 |
| hhl_8 | 2,377 | 2,365 | 2,377 | 2,377 | 1,064 | 500 | 2,375 | **275** | 329 | 337 |
| heisenberg_32 | 3,942 | 3,834 | 3,942 | 3,940 | 3,912 | 3,878 | 3,882 | – | – | **3,328** |
| grover_10 | 16,397 | 14,453 | 16,397 | 16,397 | 16,395 | 16,393 | 16,395 | – | – | **13,543** |
| hubbard_18 | 33,958 | 29,547 | 33,926 | 33,926 | 33,926 | 33,829 | 30,415 | – | – | **27,559** |

### Physical single-qubit gates (sx + x; rz is virtual)

| circuit | input | TKET (conn.-preserving) | QUESO (15 min) | GUOQ 1 min | GUOQ 5 min | GUOQ 15 min | HyPSO-QCO v1 | v2 w/o swarm | v2, 1 worker | **HyPSO-QCO v2 (15 min)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 638 | 511 | 469 | 447 | 413 | 413 | 502 | 300 | 313 | **291** |
| heisenberg_8 | 740 | 485 | **330** | 497 | 507 | 549 | 386 | 434 | 437 | 442 |
| add_17 | 907 | 806 | 766 | 701 | 699 | 682 | 798 | **599** | 651 | 606 |
| qae_17 | 982 | 873 | 836 | 779 | 687 | 706 | 882 | **682** | 756 | 686 |
| qft_16 | 1,111 | 969 | 999 | 830 | 803 | 891 | 982 | 786 | 823 | **768** |
| hubbard_8 | 2,659 | 1,889 | 2,320 | 2,293 | 1,966 | 1,747 | 2,223 | **1,267** | 1,420 | 1,373 |
| hhl_8 | 6,562 | 5,496 | 5,921 | 5,921 | 2,411 | 1,032 | 5,734 | **572** | 653 | 679 |
| heisenberg_32 | 19,206 | 5,142 | 5,305 | 5,302 | 5,249 | 5,375 | 5,353 | – | – | **4,547** |
| grover_10 | 31,156 | 20,737 | 28,182 | 28,182 | 27,234 | 27,236 | 26,710 | – | – | **14,932** |
| hubbard_18 | 116,414 | 41,731 | 48,653 | 48,653 | 48,653 | 48,581 | 48,670 | – | – | **38,453** |

### Total native gates (rz + sx + x + ecr)

| circuit | input | TKET (conn.-preserving) | QUESO (15 min) | GUOQ 1 min | GUOQ 5 min | GUOQ 15 min | HyPSO-QCO v1 | v2 w/o swarm | v2, 1 worker | **HyPSO-QCO v2 (15 min)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 1,898 | 1,402 | 1,337 | 1,258 | 1,171 | 1,170 | 1,418 | 818 | 865 | **808** |
| heisenberg_8 | 2,127 | 1,455 | 1,217 | 1,497 | 1,494 | 1,597 | 1,312 | **1,193** | 1,231 | 1,229 |
| add_17 | 2,812 | 2,203 | 2,108 | 1,955 | 1,991 | 1,980 | 2,193 | 1,677 | 1,792 | **1,662** |
| qae_17 | 3,033 | 2,368 | 2,301 | 2,191 | 1,970 | 2,057 | 2,412 | 1,890 | 2,027 | **1,860** |
| qft_16 | 3,444 | 2,651 | 2,691 | 2,401 | 2,329 | 2,568 | 2,677 | 2,202 | 2,296 | **2,144** |
| hubbard_8 | 8,125 | 5,174 | 6,204 | 6,142 | 5,462 | 4,972 | 6,002 | **3,646** | 4,065 | 3,898 |
| hhl_8 | 18,165 | 14,780 | 16,069 | 16,069 | 6,568 | 2,803 | 15,390 | **1,528** | 1,756 | 1,811 |
| heisenberg_32 | 58,848 | 14,100 | 14,544 | 14,548 | 14,449 | 14,700 | 14,740 | – | – | **12,657** |
| grover_10 | 93,235 | 57,497 | 74,687 | 74,687 | 73,272 | 73,279 | 71,485 | – | – | **48,187** |
| hubbard_18 | 357,535 | 112,902 | 131,273 | 131,273 | 131,273 | 131,025 | 135,134 | – | – | **105,965** |

### Circuit depth

| circuit | input | TKET (conn.-preserving) | QUESO (15 min) | GUOQ 1 min | GUOQ 5 min | GUOQ 15 min | HyPSO-QCO v1 | v2 w/o swarm | v2, 1 worker | **HyPSO-QCO v2 (15 min)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 1,138 | 848 | 811 | 773 | 640 | 616 | 832 | 472 | 488 | **448** |
| heisenberg_8 | 529 | 387 | **302** | 405 | 611 | 539 | 358 | 325 | 361 | 342 |
| add_17 | 1,003 | 731 | 699 | 715 | 768 | 735 | 720 | 546 | 588 | **524** |
| qae_17 | 1,066 | 777 | 747 | 714 | 629 | 649 | 779 | 550 | 595 | **547** |
| qft_16 | 1,009 | 727 | 728 | 779 | 772 | 827 | 713 | 585 | 644 | **575** |
| hubbard_8 | 4,400 | 2,852 | 3,275 | 3,250 | 2,906 | 2,654 | 3,175 | **1,922** | 2,091 | 1,996 |
| hhl_8 | 10,641 | 9,282 | 9,252 | 9,252 | 3,982 | 1,770 | 9,000 | **1,008** | 1,168 | 1,215 |
| heisenberg_32 | 7,143 | 2,297 | 2,412 | 2,422 | 2,413 | 2,580 | 2,422 | – | – | **2,089** |
| grover_10 | 43,923 | 32,145 | 35,477 | 35,477 | 35,088 | 35,093 | 34,216 | – | – | **28,941** |
| hubbard_18 | 136,644 | 45,927 | 56,476 | 56,476 | 56,476 | 56,316 | 57,219 | – | – | **42,520** |

### Estimated success probability (ECR error 7e-3, sx/x error 2.5e-4, rz free)

| circuit | input | TKET (conn.-preserving) | QUESO (15 min) | GUOQ 1 min | GUOQ 5 min | GUOQ 15 min | HyPSO-QCO v1 | v2 w/o swarm | v2, 1 worker | **HyPSO-QCO v2 (15 min)** |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| mult_8 | 0.0959 | 0.108 | 0.1 | 0.13 | 0.178 | 0.223 | 0.101 | 0.31 | 0.292 | 0.317 |
| heisenberg_8 | 0.0435 | 0.0463 | 0.0482 | 0.0472 | 0.0674 | 0.0883 | 0.0475 | 0.138 | 0.123 | 0.129 |
| add_17 | 0.0239 | 0.0253 | 0.0248 | 0.0303 | 0.0382 | 0.0438 | 0.026 | 0.056 | 0.0487 | 0.0555 |
| qae_17 | 0.0175 | 0.0185 | 0.0181 | 0.0237 | 0.0367 | 0.0415 | 0.0198 | 0.0463 | 0.0412 | 0.0441 |
| qft_16 | 0.0101 | 0.0108 | 0.0104 | 0.0117 | 0.0171 | 0.0185 | 0.0112 | 0.0214 | 0.0182 | 0.0215 |
| hubbard_8 | 4.08e-05 | 9.51e-05 | 4.7e-05 | 5.01e-05 | 9.27e-05 | 0.00018 | 4.89e-05 | 0.00118 | 0.000781 | 0.00103 |
| hhl_8 | 1.09e-08 | 1.54e-08 | 1.27e-08 | 1.27e-08 | 0.000311 | 0.023 | 1.35e-08 | 0.126 | 0.0842 | 0.0791 |
| heisenberg_32 | 7.73e-15 | 5.56e-13 | 2.5e-13 | 2.54e-13 | 3.13e-13 | 3.85e-13 | 3.76e-13 | – | – | 2.26e-11 |
| grover_10 | 3.92e-54 | 4.53e-47 | 8.25e-54 | 8.25e-54 | 1.06e-53 | 1.08e-53 | 1.21e-53 | – | – | 1.15e-43 |
| hubbard_18 | 5.77e-117 | 2.13e-95 | 1.65e-109 | 1.65e-109 | 1.65e-109 | 3.32e-109 | 8.44e-99 | – | – | 5.61e-89 |

### Mean reductions over the circuits each method completed

| method | mean ecr reduction vs input | geo-mean ratio | circuits |
|---|---:|---:|---:|
| TKET (conn.-preserving) | 4.1 % | 0.958 | 10 |
| QUESO (15 min) | 0.1 % | 0.999 | 10 |
| GUOQ 1 min | 2.7 % | 0.972 | 10 |
| GUOQ 5 min | 14.1 % | 0.840 | 10 |
| GUOQ 15 min | 20.2 % | 0.744 | 10 |
| HyPSO-QCO v1 | 1.9 % | 0.980 | 10 |
| v2 w/o swarm | 38.3 % | 0.535 | 7 |
| v2, 1 worker | 35.1 % | 0.572 | 7 |
| **HyPSO-QCO v2 (15 min)** | 31.3 % | 0.626 | 10 |

| method | mean oneq_phys reduction vs input | geo-mean ratio | circuits |
|---|---:|---:|---:|
| TKET (conn.-preserving) | 30.5 % | 0.651 | 10 |
| QUESO (15 min) | 28.5 % | 0.667 | 10 |
| GUOQ 1 min | 29.5 % | 0.667 | 10 |
| GUOQ 5 min | 38.0 % | 0.585 | 10 |
| GUOQ 15 min | 39.5 % | 0.542 | 10 |
| HyPSO-QCO v1 | 27.7 % | 0.679 | 10 |
| v2 w/o swarm | 47.4 % | 0.450 | 7 |
| v2, 1 worker | 43.7 % | 0.485 | 7 |
| **HyPSO-QCO v2 (15 min)** | 52.2 % | 0.421 | 10 |

| method | mean gates reduction vs input | geo-mean ratio | circuits |
|---|---:|---:|---:|
| TKET (conn.-preserving) | 36.2 % | 0.597 | 10 |
| QUESO (15 min) | 33.7 % | 0.623 | 10 |
| GUOQ 1 min | 34.6 % | 0.617 | 10 |
| GUOQ 5 min | 42.1 % | 0.545 | 10 |
| GUOQ 15 min | 43.4 % | 0.507 | 10 |
| HyPSO-QCO v1 | 33.0 % | 0.632 | 10 |
| v2 w/o swarm | 51.7 % | 0.416 | 7 |
| v2, 1 worker | 48.5 % | 0.448 | 7 |
| **HyPSO-QCO v2 (15 min)** | 55.6 % | 0.393 | 10 |

| HyPSO-QCO v2 vs | ecr: wins / ties / losses | one-sided Wilcoxon p |
|---|---|---:|
| TKET (conn.-preserving) | 10 / 0 / 0 | 0.0010 |
| QUESO (15 min) | 10 / 0 / 0 | 0.0010 |
| GUOQ 1 min | 10 / 0 / 0 | 0.0010 |
| GUOQ 5 min | 10 / 0 / 0 | 0.0010 |
| GUOQ 15 min | 10 / 0 / 0 | 0.0010 |
| HyPSO-QCO v1 | 10 / 0 / 0 | 0.0010 |
| v2 w/o swarm | 1 / 1 / 5 | 0.9688 |
| v2, 1 worker | 6 / 0 / 1 | 0.0391 |

| HyPSO-QCO v2 vs | gates: wins / ties / losses | one-sided Wilcoxon p |
|---|---|---:|
| TKET (conn.-preserving) | 10 / 0 / 0 | 0.0010 |
| QUESO (15 min) | 9 / 0 / 1 | 0.0020 |
| GUOQ 1 min | 10 / 0 / 0 | 0.0010 |
| GUOQ 5 min | 10 / 0 / 0 | 0.0010 |
| GUOQ 15 min | 10 / 0 / 0 | 0.0010 |
| HyPSO-QCO v1 | 10 / 0 / 0 | 0.0010 |
| v2 w/o swarm | 4 / 0 / 3 | 0.7109 |
| v2, 1 worker | 6 / 0 / 1 | 0.0234 |

### Runtime (s) and verification

Deviation: random-state (<= 20 qubits) or Choi-MPS (> 20 qubits) distance to the input, maximum over seeds; < 1e-9 exact, < 1e-6 numerically exact, otherwise approximate.

| circuit | method | seeds | mean time (s) | max deviation | check | coupling / ECR directions |
|---|---|---:|---:|---:|---|---|
| mult_8 | TKET (conn.-preserving) | 1 | 2 | 1.1e-14 | statevector | ok |
| mult_8 | QUESO (15 min) | 1 | 900 | 1.1e-14 | statevector | ok |
| mult_8 | GUOQ 1 min | 1 | 60 | 6.8e-10 | statevector | ok |
| mult_8 | GUOQ 5 min | 1 | 300 | 3.4e-08 | statevector | ok |
| mult_8 | GUOQ 15 min | 1 | 900 | 6.4e-08 | statevector | ok |
| mult_8 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| mult_8 | v2 w/o swarm | 1 | 900 | 1.1e-10 | statevector | ok |
| mult_8 | v2, 1 worker | 1 | 900 | 1.9e-10 | statevector | ok |
| mult_8 | **HyPSO-QCO v2 (15 min)** | 1 | 900 | 3.7e-09 | statevector | ok |
| heisenberg_8 | TKET (conn.-preserving) | 1 | 3 | 1.5e-14 | statevector | ok |
| heisenberg_8 | QUESO (15 min) | 1 | 900 | 5.5e-14 | statevector | ok |
| heisenberg_8 | GUOQ 1 min | 1 | 60 | 8.1e-10 | statevector | ok |
| heisenberg_8 | GUOQ 5 min | 1 | 300 | 5.6e-08 | statevector | ok |
| heisenberg_8 | GUOQ 15 min | 1 | 900 | 4.9e-07 | statevector | ok |
| heisenberg_8 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| heisenberg_8 | v2 w/o swarm | 1 | 900 | 1.7e-08 | statevector | ok |
| heisenberg_8 | v2, 1 worker | 1 | 900 | 3.1e-09 | statevector | ok |
| heisenberg_8 | **HyPSO-QCO v2 (15 min)** | 1 | 900 | 6.7e-09 | statevector | ok |
| add_17 | TKET (conn.-preserving) | 1 | 3 | 2.1e-12 | statevector | ok |
| add_17 | QUESO (15 min) | 1 | 900 | 2.1e-12 | statevector | ok |
| add_17 | GUOQ 1 min | 1 | 60 | 2.1e-12 | statevector | ok |
| add_17 | GUOQ 5 min | 1 | 300 | 4.3e-08 | statevector | ok |
| add_17 | GUOQ 15 min | 1 | 900 | 4.7e-08 | statevector | ok |
| add_17 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| add_17 | v2 w/o swarm | 1 | 901 | 3.8e-11 | statevector | ok |
| add_17 | v2, 1 worker | 1 | 901 | 2.1e-10 | statevector | ok |
| add_17 | **HyPSO-QCO v2 (15 min)** | 1 | 900 | 1.5e-10 | statevector | ok |
| qae_17 | TKET (conn.-preserving) | 1 | 3 | 9.7e-10 | statevector | ok |
| qae_17 | QUESO (15 min) | 1 | 900 | 9.7e-10 | statevector | ok |
| qae_17 | GUOQ 1 min | 1 | 60 | 9.7e-10 | statevector | ok |
| qae_17 | GUOQ 5 min | 1 | 300 | 1.1e-08 | statevector | ok |
| qae_17 | GUOQ 15 min | 1 | 900 | 6.5e-08 | statevector | ok |
| qae_17 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| qae_17 | v2 w/o swarm | 1 | 901 | 4.7e-09 | statevector | ok |
| qae_17 | v2, 1 worker | 1 | 901 | 2.9e-09 | statevector | ok |
| qae_17 | **HyPSO-QCO v2 (15 min)** | 1 | 900 | 8.0e-09 | statevector | ok |
| qft_16 | TKET (conn.-preserving) | 1 | 3 | 2.3e-09 | statevector | ok |
| qft_16 | QUESO (15 min) | 1 | 900 | 2.3e-09 | statevector | ok |
| qft_16 | GUOQ 1 min | 1 | 60 | 3.3e-09 | statevector | ok |
| qft_16 | GUOQ 5 min | 1 | 300 | 2.8e-08 | statevector | ok |
| qft_16 | GUOQ 15 min | 1 | 900 | 5.4e-06 | statevector | ok |
| qft_16 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| qft_16 | v2 w/o swarm | 1 | 901 | 5.7e-08 | statevector | ok |
| qft_16 | v2, 1 worker | 1 | 901 | 2.8e-09 | statevector | ok |
| qft_16 | **HyPSO-QCO v2 (15 min)** | 1 | 901 | 2.3e-09 | statevector | ok |
| hubbard_8 | TKET (conn.-preserving) | 1 | 12 | 6.8e-14 | statevector | ok |
| hubbard_8 | QUESO (15 min) | 1 | 900 | 2.8e-14 | statevector | ok |
| hubbard_8 | GUOQ 1 min | 1 | 60 | 1.9e-08 | statevector | ok |
| hubbard_8 | GUOQ 5 min | 1 | 300 | 6.8e-08 | statevector | ok |
| hubbard_8 | GUOQ 15 min | 1 | 900 | 8.0e-08 | statevector | ok |
| hubbard_8 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| hubbard_8 | v2 w/o swarm | 1 | 901 | 1.4e-08 | statevector | ok |
| hubbard_8 | v2, 1 worker | 1 | 906 | 4.4e-09 | statevector | ok |
| hubbard_8 | **HyPSO-QCO v2 (15 min)** | 1 | 904 | 4.4e-09 | statevector | ok |
| hhl_8 | TKET (conn.-preserving) | 1 | 20 | 9.2e-14 | statevector | ok |
| hhl_8 | QUESO (15 min) | 1 | 900 | 7.9e-14 | statevector | ok |
| hhl_8 | GUOQ 1 min | 1 | 60 | 7.9e-14 | statevector | ok |
| hhl_8 | GUOQ 5 min | 1 | 300 | 7.6e-09 | statevector | ok |
| hhl_8 | GUOQ 15 min | 1 | 900 | 2.0e-08 | statevector | ok |
| hhl_8 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| hhl_8 | v2 w/o swarm | 1 | 901 | 3.4e-09 | statevector | ok |
| hhl_8 | v2, 1 worker | 1 | 901 | 4.9e-10 | statevector | ok |
| hhl_8 | **HyPSO-QCO v2 (15 min)** | 1 | 903 | 4.9e-10 | statevector | ok |
| heisenberg_32 | TKET (conn.-preserving) | 1 | 30 | 3.5e-09 | choi-mps | ok |
| heisenberg_32 | QUESO (15 min) | 1 | 900 | 3.8e-09 | choi-mps | ok |
| heisenberg_32 | GUOQ 1 min | 1 | 60 | 3.9e-09 | choi-mps | ok |
| heisenberg_32 | GUOQ 5 min | 1 | 300 | 4.0e-09 | choi-mps | ok |
| heisenberg_32 | GUOQ 15 min | 1 | 900 | 3.3e-09 | choi-mps | ok |
| heisenberg_32 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| heisenberg_32 | **HyPSO-QCO v2 (15 min)** | 1 | 904 | 1.6e-10 | choi-mps | ok |
| grover_10 | TKET (conn.-preserving) | 1 | 243 | 8.4e-13 | statevector | ok |
| grover_10 | QUESO (15 min) | 1 | 900 | 8.1e-13 | statevector | ok |
| grover_10 | GUOQ 1 min | 1 | 60 | 8.1e-13 | statevector | ok |
| grover_10 | GUOQ 5 min | 1 | 300 | 6.2e-10 | statevector | ok |
| grover_10 | GUOQ 15 min | 1 | 900 | 6.2e-10 | statevector | ok |
| grover_10 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| grover_10 | **HyPSO-QCO v2 (15 min)** | 1 | 926 | 2.9e-08 | statevector | ok |
| hubbard_18 | TKET (conn.-preserving) | 1 | 244 | – | – | ok |
| hubbard_18 | QUESO (15 min) | 1 | 900 | – | – | ok |
| hubbard_18 | GUOQ 1 min | 1 | 60 | – | – | ok |
| hubbard_18 | GUOQ 5 min | 1 | 300 | – | – | ok |
| hubbard_18 | GUOQ 15 min | 1 | 900 | – | – | ok |
| hubbard_18 | HyPSO-QCO v1 | 1 | – | – | – | ok |
| hubbard_18 | **HyPSO-QCO v2 (15 min)** | 1 | 931 | – | – | ok |
