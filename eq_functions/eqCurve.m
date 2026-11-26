function eq = eqCurve(f, f0, gdB, Q, fs)
 eq = zeros(size(f));
 for k = 1:numel(f0), eq = eq + peq_response(f, f0(k), gdB(k), Q(k), fs); end
end
