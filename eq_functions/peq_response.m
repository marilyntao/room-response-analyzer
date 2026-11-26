function eq_dB = peq_response(f, f0, G, Q, fs)
A      = 10^(G/40);
w0     = 2*pi*f0/fs;
alpha  = sin(w0)/(2*Q);
b = [ [1+(alpha*A)] , -2*cos(w0) , [1-(alpha*A)] ];     % b0 b1 b2
a = [ [1+(alpha/A)] , -2*cos(w0) , [1-(alpha/A)] ];    % a0 a1 a2
H  = freqz(b, a, f, fs);     % complex response at your frequencies
eq_dB = 20*log10(abs(H));
end
