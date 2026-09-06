# OP-X-012E.15 — Historical TE population validation closure

Frozen first-pass validation. CFB25/26 observations were not used to refit any model.

## Population integrity

- CFB25: pages=693; terminal=694/404; TE N=543/543; missing=0; duplicates=0; fetch_failures=0; parse_failures=0; archetypes={'Gritty Possession': 201, 'Pure Blocker': 162, 'UNKNOWN': 1, 'Vertical Threat': 179}; complete=False.
- CFB26: pages=676; terminal=677/404; TE N=657/657; missing=0; duplicates=0; fetch_failures=0; parse_failures=0; archetypes={'Gritty Possession': 67, 'Physical Route Runner': 403, 'Pure Blocker': 63, 'Vertical Threat': 124}; complete=True.

## Frozen-model results

- CFB25 TE-MODEL-001 v1.1 / Gritty Possession: N=201; pairs=19426; correct=19413; inversions=13; ties=0; ranking_accuracy=99.9331% MAE=5.9253; SUPPORTED.
- CFB26 TE-MODEL-001 v1.1 / Gritty Possession: N=67; pairs=2137; correct=2116; inversions=21; ties=0; ranking_accuracy=99.0173% MAE=4.6672; SUPPORTED.
- CFB25 TE-MODEL-006 v1.3 / Vertical Threat: N=179; pairs=15464; correct=15391; inversions=73; ties=0; ranking_accuracy=99.5279% MAE=6.6722; SUPPORTED.
- CFB26 TE-MODEL-006 v1.3 / Vertical Threat: N=124; pairs=7342; correct=7328; inversions=13; ties=1; ranking_accuracy=99.8229% MAE=4.6331; SUPPORTED.
- CFB25 TE-MODEL-003 v1.1 / Physical Route Runner: N=0; INSUFFICIENT EVIDENCE.
- CFB26 TE-MODEL-003 v1.1 / Physical Route Runner: N=403; pairs=78439; correct=78295; inversions=144; ties=0; ranking_accuracy=99.8164% MAE=4.3415; SUPPORTED.
- CFB25 TE-MODEL-004 v1.1 / Pure Blocker: N=162; pairs=12218; correct=11873; inversions=338; ties=7; ranking_accuracy=97.2320% MAE=7.8130; SUPPORTED WITH EXCEPTIONS.
- CFB26 TE-MODEL-004 v1.1 / Pure Blocker: N=63; pairs=1798; correct=1794; inversions=4; ties=0; ranking_accuracy=99.7775% MAE=2.9352; SUPPORTED.

## Failure science

- CFB25 Gritty Possession: 13 inversions; 0 meaningful (score deficit >=1 or OVR gap >=2).
  - Jack Velling 93 (85.030) < Terrance Carter 92 (85.570); delta=-0.540; gap=1.
  - Mason Taylor 93 (85.120) < Terrance Carter 92 (85.570); delta=-0.450; gap=1.
  - Jack Velling 93 (85.030) < Tyler Neville 92 (85.340); delta=-0.310; gap=1.
  - Mason Taylor 93 (85.120) < Tyler Neville 92 (85.340); delta=-0.220; gap=1.
  - Lake McRee 82 (75.000) < D J Thomas-Jones 81 (75.180); delta=-0.180; gap=1.
- CFB25 Vertical Threat: 73 inversions; 38 meaningful (score deficit >=1 or OVR gap >=2).
  - Trey McBride 91 (80.524) < Vernon Davis 90 (83.631); delta=-3.107; gap=1.
  - Trey McBride 90 (79.718) < Hunter Henry 89 (82.777); delta=-3.058; gap=1.
  - Trey McBride 91 (80.524) < Elijah Arroyo 90 (83.563); delta=-3.039; gap=1.
  - Trey McBride 88 (78.107) < Cooper Flanagan 87 (80.932); delta=-2.825; gap=1.
  - Trey McBride 89 (78.913) < Kyle Pitts 88 (81.738); delta=-2.825; gap=1.
- CFB25 Physical Route Runner: 0 inversions; 0 meaningful (score deficit >=1 or OVR gap >=2).
- CFB25 Pure Blocker: 338 inversions; 76 meaningful (score deficit >=1 or OVR gap >=2).
  - Preston Howard 70 (61.100) < Duke Olges 69 (62.970); delta=-1.870; gap=1.
  - Marshall Lang 70 (61.470) < Duke Olges 69 (62.970); delta=-1.500; gap=1.
  - Preston Howard 70 (61.100) < Reid Mitchell 69 (62.600); delta=-1.500; gap=1.
  - Carson Kent 67 (58.670) < James Dodd 66 (60.100); delta=-1.430; gap=1.
  - Sam Hart 70 (61.570) < Duke Olges 69 (62.970); delta=-1.400; gap=1.
- CFB26 Gritty Possession: 21 inversions; 7 meaningful (score deficit >=1 or OVR gap >=2).
  - Jameson Geers 75 (67.660) < Lukas Ungar 74 (70.240); delta=-2.580; gap=1.
  - Luke Lindenmeyer 74 (67.000) < Jackson Bowers 73 (68.100); delta=-1.100; gap=1.
  - Brandon Frazier 75 (69.180) < Lukas Ungar 74 (70.240); delta=-1.060; gap=1.
  - Jameson Geers 75 (67.660) < Landon Morris 74 (68.680); delta=-1.020; gap=1.
  - Alge Crumpler 95 (90.170) < Heath Miller 94 (90.810); delta=-0.640; gap=1.
- CFB26 Vertical Threat: 13 inversions; 0 meaningful (score deficit >=1 or OVR gap >=2).
  - George Burhenn 71 (66.165) < Karson Gay 70 (66.553); delta=-0.388; gap=1.
  - Kamron Beachem 70 (65.621) < J T Taggart 69 (66.010); delta=-0.388; gap=1.
  - Elija Walton 70 (65.660) < J T Taggart 69 (66.010); delta=-0.350; gap=1.
  - George Burhenn 71 (66.165) < Tae'Shaun Gelsey 70 (66.485); delta=-0.320; gap=1.
  - Jaleel Skinner 79 (74.175) < Elija Lofton 78 (74.437); delta=-0.262; gap=1.
- CFB26 Physical Route Runner: 144 inversions; 0 meaningful (score deficit >=1 or OVR gap >=2).
  - Dallen Bentley 78 (72.316) < Nate Kurisky 77 (73.311); delta=-0.995; gap=1.
  - Will Kacmarek 81 (75.406) < Preston Howard 80 (76.333); delta=-0.927; gap=1.
  - Dallen Bentley 78 (72.316) < Elyiss Williams 77 (73.156); delta=-0.840; gap=1.
  - Blake Smith 88 (82.173) < Conner Cravaack 87 (82.985); delta=-0.813; gap=1.
  - Josh Cuevas 79 (73.813) < Jordan Dingle 78 (74.597); delta=-0.784; gap=1.
- CFB26 Pure Blocker: 4 inversions; 1 meaningful (score deficit >=1 or OVR gap >=2).
  - Dorian Thomas 96 (90.180) < Josh Phifer 95 (90.430); delta=-0.250; gap=1.
  - Dorian Thomas 96 (90.180) < Isaac Schoenfeld 95 (90.410); delta=-0.230; gap=1.
  - Brett Seither 88 (82.510) < Triston O'Brien 86 (82.700); delta=-0.190; gap=2.
  - Peyton Warford 70 (66.710) < Tyson Chavez 69 (66.730); delta=-0.020; gap=1.

## E.15 classification

**INCOMPLETE**

Ranking accuracy is the primary validation measure. Raw weighted-score/OVR MAE is diagnostic only; the frozen weights are not asserted to be the exact displayed-OVR conversion formula.
