# Round2 forward-model knowledge

Evidence classes: implementation facts, modeling assumptions, source literature and project findings. Numerical success supports the configuration evaluated. ART-to-PLETH shape agreement does not identify unique physiology.

## Signals, time and units

ART input is mmHg; time is seconds; frequency is Hz. Native SNUADC tracks are500Hz; fit inputs are50Hz after resampling, and final timing features are500Hz. Each approved window is30s wholly inside the first80% of its record. End effects use constant extension and an analysis edge mask. Keep physical-time ensembles; do not warp beat duration to a phase axis.

## Model ladder and parameters

All modules expose predict(art,params)->dA and PARAM_BOUNDS/PARAM_PRIORS/DEFAULT_PARAMS. Priors are declared uniform engineering search bounds; fitted coordinates are effective predictive parameters.

- M0: second-order lowpass multiplied by two lead/lag sections H(s)=(1+s/wz)/(1+s/wp), giving4poles/2zeros. Frequency0.3-20Hz; damping0.15-3; each added pole/zero0.3-20Hz. Equal pole/zero pairs exactly recover M1.
- M1: H(s)=wn^2/(s^2+2*zeta*wn*s+wn^2), V=C*P with fixed scale. Frequency0.3-20Hz,zeta0.15-3. Output is a scaled pressure/area proxy.
- M2: M1 transmission followed by V/Vscale=1/2+atan((P-Pexternal-Pmid)/width)/pi. Pmid[-20,120]mmHg,width[5,120]mmHg,Pexternal=0 fixes the coordinate. Retain pressure DC before this nonlinear operation.
- M3: import peripheral_ppg.model.local_model. FixedRin/Rout=1000/1500mmHg*s/mL; free identifiable tau=C*(Rin||Rout) in[.02,2]s. Output volume in mL is scaled by the window nuisance gain.
- M4: linear tapered radial-to-digital frequency-domain line. dP/dx=-(R+iwL)Q, dQ/dx=-iwCP; R=8*pi*mu/A^2,L=rho/A,C=A/(rho*c^2). Terminal parallelRC Zbed=Rbed/(1+iw*tau). GeometryL=.25m,inlet radius=.0015m,rho1060kg/m3,mu=.004Pa*s;24midpoint segments with linear-radius taper. Freec[3,20]m/s,taper[.3,1],terminal resistance ratio[.5,30],bedtau[.02,1]s. Convert mmHg toPa before fractional area output.

No model includes a separate free pure delay; external residual PTT owns that coordinate. M4 retains its physical propagation phase. Constant output scales are removed by normalized comparison/profiled window gain.

## Catheter and observation operator

Catheter H(f)=1/(1-(f/fn)^2+2i*zeta*f/fn). Round1 successive-peak frequency is damped fd, so fn=fd/sqrt(1-zeta^2) under the underdamped second-order assumption. Candidates remain unverified until inspected using ART-only strips. Missing estimates make correction unavailable. Both branches receive W(f)=1/(1+(f/15)^8); only the corrected branch additionally receives1/H.

PLETH(t)=g_window*BP[sign*dA(t-device_delay-PTT_case)]+offset_window. Fit global corners/order/sign with uncorrected M0 using case-balanced pilot loss; causal phase is primary. Fix device_delay=.4s as a gauge, residualPTT[-.4,.5]s,total pure delay[0,.9]s. Per-case physiological parameters and PTT are shared across windows. Window gain is positive. Filters and device/physiological delays are operationally confounded; the components are not separately measured.

## Fitting and metrics

Fit variance-normalized physical-waveform residuals with profiled positive gain/offset. Foot alignment removes pure delay, so the primary shape endpoint is reported separately. Detect feet identically in observed/predicted signals using the frozen smoothed-upstroke/local-minimum rule. Normalize each beat once, then form full/odd/even means on common physical-time support.

PrimaryNMSE=sum((prediction-target)^2)/sum((target-mean(target))^2)=1-R2. Noise floor uses n1*n2/(n1+n2)^2 times odd/even squared difference divided by full-target centered sum of squares; this is1/4 for equal halves under independent exchangeable residuals. CeilingR2=1-noise_floor; report raw agreement, invalid cases and coverage. P2 requiresmodelR2>=.9*ceilingR2 and the predeclared M0 NMSE margin.

Features: foot-to-peak upstroke time, notch presence/time/depth, systolic width and delay residual. Retain missing-notch cases/coverage. P5 uses MAP-separatedpairs(abs difference>=15mmHg), fitA physiology, predictB refittinggain/offset/PTT only; degradation is transferredB NMSE minus independentB diagnostic-fit NMSE. Aggregate windows/pairs within case first.

P6 fits low/high corners continuously per case with global order/sign/phase fixed and uncorrected M0 nuisance parameters. Boundslo[.05,1],hi[5,15]Hz; starts at frozen corners and bounds midpoint. Reporteachcornermean/sampleSD/CV,casecount,boundhits,lossesandstartdependence. This tests operational consistency, not physiological separation.

## Amended P7 optics

Absorptionmix mua=f_b*mua_blood+(1-f_b)*mua_matrix. Fixed-scatter detected-photon reweighting uses baselineweights and X=sum(delta_mua_i*L_i), L inmm. ln(I1/I0)=ln(Ew exp(-X))=-EwX+.5VarwX+...; quadratic/linear=.5VarwX/abs(EwX). Exact remainder/linear=abs(ln(Ew exp(-X))+EwX)/abs(EwX). Use the same photons, stable logarithms and between-seed uncertainty. OpticalAC/DC is peak-to-peak intensity divided bymean, as in peripheral_ppg.analysis.ac_dc; up toabout5% is an engineering bound, not a DC estimate from band-pass/AGC PLETH. Baselinef_b1-10%,SpO2.90-1.00,660/940nm. Report maximum over the frozen sampled grid and the1%criterion.

Scattering sensitivity is reporting-only atf0=.10,SpO2=.98,multipliers1.5/2,660/940nm,10paired seeds. Volume-mix mus andg inlabel2; label3 remains canonical in every arm. BaselineB already usesf0mixedscatter;A changes absorption only;T changes absorption+scatter. Reportseedwise pairedlog changes andSE, plusabsorption-firstsignedshare(mean(logIT-logIA)/mean(logIT-logIB)). If total change's95%t9intervalcontains0, share isundefined andabsoluteincrement remains reported.

Theoretical oxygenatedblood,Hct45% sensitivity inputs from [Bosschaart etal.,2014appendix](https://pmc.ncbi.nlm.nih.gov/articles/PMC3953607/):660nm mus92.29/mm,g.9850;940nm56.84/mm,g.9768. These are engineering assumptions atSpO2=.98. [Prahl hemoglobin spectra](https://omlc.org/spectra/hemoglobin/summary.html) supply saturation-dependent absorption; mu_a(mm^-1)=2.303*epsilon(cm^-1/M)*150(g/L)/64500(g/mol)/10.

## Stage decisions and exclusions

P1-P7 definitions and thresholds are finalized in workspace PREREG after pilot, committed separately, then frozen. Gate1 authorizes batch; Gate2 authorizes one Validation evaluation. Round3 recommendation follows the workspace decision rules. This round covers normalized forwardshape/timing; inversion,BPlevel/SBP/DBP,amplitude/ACDC fitting,per-case3DMCX,wrist/ringmodels andunregistered modelvariants are excluded.
