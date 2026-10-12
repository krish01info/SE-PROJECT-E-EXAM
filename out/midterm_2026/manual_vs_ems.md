# Manual mid-term plan vs EMS plan

Dataset: Mid-term exams, March 2026 (reconstructed from the master sheet). Both plans are measured on the same reconstructed registrations (1502 students, 4486 paper-sittings), with 30-seat rooms and no two neighbours writing the same paper.

| Measure | Manual plan (sheet) | EMS |
|---|---|---|
| Students with two papers in the same slot | 0 | 0 |
| Students with two papers on the same day | 167 | 0 |
| Students with papers on consecutive days | 999 | 1360 |
| Slots used | 8 | 6 |
| Room-slots needed (neighbours separated) | 193 | 166 |
| Peak rooms in one slot | 56 | 33 |
| Invigilation duties (2 per room) | 386 | 332 |
| Peak invigilators in one slot | 112 | 66 |

## Manual plan by slot

| Slot | Papers | Students | Rooms needed |
|---|---|---|---|
| 2026-03-23 Morning | SKL2711 CSE3722 MTH1803 MTH1802 | 1121 | 43 |
| 2026-03-24 Morning | MTH2801 CSE3702 | 894 | 33 |
| 2026-03-24 Afternoon | FIN1001 | 42 | 3 |
| 2026-03-25 Morning | PRJ1101 CSE2029 PSP4706 | 1324 | 56 |
| 2026-03-25 Afternoon | PSP1805 | 180 | 12 |
| 2026-03-26 Morning | ECE1101 CSE4007 CSE3726 | 484 | 17 |
| 2026-03-26 Afternoon | ECE2016 | 17 | 2 |
| 2026-03-27 Morning | CSE3703 ECE2705 MEC2025 | 424 | 27 |

## EMS plan by slot

| Slot | Papers | Students | Rooms needed |
|---|---|---|---|
| 2026-03-23 Morning | CSE3703 MTH1803 MTH1802 FIN1001 ECE2016 | 755 | 27 |
| 2026-03-24 Afternoon | MTH2801 CSE3722 ECE2705 | 896 | 33 |
| 2026-03-25 Morning | PRJ1101 CSE3702 | 894 | 33 |
| 2026-03-26 Morning | CSE2029 PSP4706 MEC2025 | 851 | 29 |
| 2026-03-26 Afternoon | PSP1805 | 180 | 12 |
| 2026-03-27 Morning | SKL2711 ECE1101 CSE4007 CSE3726 | 910 | 32 |

(EMS rooms per slot here use the same estimator as the manual plan; the rooms EMS actually opened are in `slot_summary.csv` and in the table above.)
