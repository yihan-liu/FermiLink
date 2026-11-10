#=
Copyright 2015-2026 INSIGNEO Institute for in silico Medicine

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
=#

@inline function _write_waveform_row!(w, idx, t, x1, x2, x3, x4, x5)
    @inbounds w[idx,1]=t; w[idx,2]=x1; w[idx,3]=x2; w[idx,4]=x3; w[idx,5]=x4; w[idx,6]=x5
end

function save_waveforms(idx::Int64, t::Float64, v::Vessel)
    n2, n3, n4, M = v.node2, v.node3, v.node4, v.M
    haskey(v.waveforms,"A") && _write_waveform_row!(v.waveforms["A"],idx,t,
        v.A[1],v.A[n2],v.A[n3],v.A[n4],v.A[M])
    haskey(v.waveforms,"Q") && _write_waveform_row!(v.waveforms["Q"],idx,t,
        v.Q[1],v.Q[n2],v.Q[n3],v.Q[n4],v.Q[M])
    haskey(v.waveforms,"u") && _write_waveform_row!(v.waveforms["u"],idx,t,
        v.u[1],v.u[n2],v.u[n3],v.u[n4],v.u[M])
    pval(i) = begin
        elastic_pressure = pressure(v.A[i], v.A0[i], v.beta[i], v.Pext) - v.Pout
        v.viscous_pressure && v.viscoelastic ?
            elastic_pressure + v.Gamma_in[i] / sqrt(v.A[i]) * v.adot[i] :
            elastic_pressure
    end
    haskey(v.waveforms,"P") && _write_waveform_row!(v.waveforms["P"],idx,t,
        pval(1), pval(n2), pval(n3), pval(n4), pval(M))
    return
end


function swap_waveforms!(v::Vessel)
    v.waveforms, v.waveforms_prev = v.waveforms_prev, v.waveforms
end

function flush_waveforms(v::Vessel)
    for k in keys(v.waveforms)
        open("$(v.label)_$k.last", "w") do io
            writedlm(io, v.waveforms[k], " ")
        end
    end
end


function append_last_to_out(v::Vessel)
    for k in keys(v.waveforms)
        open("$(v.label)_$k.out", "a") do io
            last = readdlm(v.label * "_$k.last")
            writedlm(io, last, " ")
        end
    end
end
