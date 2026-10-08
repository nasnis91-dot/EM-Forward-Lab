r"""Konten Mode Belajar dalam Bahasa Indonesia (persamaan sama dengan versi Inggris)."""

TOPICS = {}

TOPICS["Ikhtisar & konvensi"] = r"""
<h2>EM-Forward Lab — apa yang dihitung</h2>
<p>Program menghitung <b>impedansi permukaan</b> gelombang elektromagnetik bidang yang merambat ke dalam bumi,
untuk model berlapis 1D dan model 2D. Dari impedansi diperoleh resistivitas semu dan fase yang diukur
pada survei MT, AMT, dan VLF-R.</p>
<h3>Konvensi</h3>
<ul>
<li>Ketergantungan waktu <b>exp(+iωt)</b>; pendekatan kuasi-statis (arus perpindahan diabaikan).</li>
<li>Koordinat: x = arah jurus (strike), y = profil, z positif ke <b>bawah</b>. μ = μ₀ = 4π×10⁻⁷ H/m.</li>
<li>Impedansi Z = E<sub>x</sub>/H<sub>y</sub> (TE). Mode TM ditulis −E<sub>y</sub>/H<sub>x</sub>, sehingga
kedua mode memberi fase +45° pada setengah ruang homogen.</li>
</ul>
[[EQ: $\rho_a = \dfrac{|Z|^2}{\omega\mu_0},\qquad \varphi = \arg(Z),\qquad \omega = 2\pi f$]]
<p>Setengah ruang homogen memberi ρ<sub>a</sub> = ρ dan φ = 45° pada semua frekuensi.
φ &gt; 45° menunjukkan resistivitas <i>menurun</i> terhadap kedalaman; φ &lt; 45° <i>meningkat</i>.</p>
<h3>Asumsi sumber</h3>
<p>Semua respons memakai <b>sumber gelombang bidang</b>. Ini standar untuk MT dan AMT (sumber alami) dan
berlaku untuk VLF-R hanya pada medan jauh pemancar (jarak ≫ skin depth).</p>
"""

TOPICS["Magnetotellurik (MT)"] = r"""
<h2>Magnetotellurik (MT)</h2>
<p><b>Sumber:</b> medan magnet alami yang berubah terhadap waktu. Di bawah ~1 Hz berasal dari interaksi angin
matahari dengan magnetosfer/ionosfer; di atas ~1 Hz dari petir di seluruh dunia (sferics).</p>
<p><b>Yang diukur:</b> medan listrik (E<sub>x</sub>, E<sub>y</sub>) dan magnet (H<sub>x</sub>, H<sub>y</sub>)
horizontal; hubungannya adalah tensor impedansi:</p>
[[EQ: $E_x = Z_{xx}H_x + Z_{xy}H_y,\qquad E_y = Z_{yx}H_x + Z_{yy}H_y$]]
<p>Untuk 1D: Z<sub>xx</sub> = Z<sub>yy</sub> = 0 dan Z<sub>xy</sub> = −Z<sub>yx</sub>. Untuk 2D (koordinat
strike) kedua elemen off-diagonal adalah respons TE dan TM.</p>
<p><b>Rentang:</b> 10⁻⁴ – 10³ Hz. Kedalaman: ratusan meter hingga ratusan kilometer — kerak, mantel atas,
sistem panas bumi, cekungan sedimen, zona sesar.</p>
"""

TOPICS["Audio Magnetotellurik (AMT)"] = r"""
<h2>Audio Magnetotellurik (AMT)</h2>
<p>Fisika sama dengan MT pada frekuensi audio (≈ 1 Hz – 100 kHz). Sumber utama: aktivitas petir global.
Karena frekuensi lebih tinggi, skin depth lebih kecil: AMT mencitrakan ~1–2 km teratas.</p>
<p>Catatan lapangan: sekitar 1–5 kHz sinyal alami lemah (<i>dead band</i> AMT). Ini menurunkan kualitas data
nyata, tetapi tidak mengubah respons forward.</p>
<p>Aplikasi: lapisan penudung lempung (clay cap) panas bumi, eksplorasi mineral, air tanah, sesar dangkal.</p>
"""

TOPICS["VLF-Resistivitas (VLF-R)"] = r"""
<h2>VLF-Resistivitas (VLF-R)</h2>
<p><b>Sumber:</b> pemancar navigasi militer 15–30 kHz (mis. NWC Australia 19,8 kHz, yang biasa dipakai di
Indonesia). Jaraknya ribuan km, sehingga di lokasi survei medannya berupa <b>gelombang bidang</b>.</p>
<p><b>Yang diukur:</b> E horizontal dan H horizontal tegak lurus → ρ<sub>a</sub> dan φ di setiap stasiun.</p>
<p><b>Mode:</b> azimut pemancar terhadap jurus geologi menentukan mode: E sejajar jurus → TE; E tegak lurus
jurus → TM (respons lebih tajam di kontak).</p>
<p><b>Kedalaman:</b> pada 20 kHz skin depth ~36 m di 100 Ω·m dan ~11 m di 10 Ω·m — metode dangkal.</p>
<p><b>Cek medan jauh:</b> program menampilkan r/δ dan menandai frekuensi dengan r/δ &lt; 5.</p>
"""

TOPICS["Pemodelan kedepan 1D"] = r"""
<h2>Bumi berlapis 1D — rekursi impedansi</h2>
<p>Lapisan j memiliki resistivitas ρ<sub>j</sub> (σ<sub>j</sub> = 1/ρ<sub>j</sub>) dan ketebalan h<sub>j</sub>;
lapisan terakhir adalah setengah ruang. Di tiap lapisan:</p>
[[EQ: $\dfrac{d^2E_x}{dz^2} = i\omega\mu_0\sigma_j\,E_x = k_j^2E_x,\qquad k_j=\sqrt{i\omega\mu_0\sigma_j}$]]
<p>dengan impedansi intrinsik</p>
[[EQ: $Z_j^0=\sqrt{\dfrac{i\omega\mu_0}{\sigma_j}} = \dfrac{i\omega\mu_0}{k_j}$]]
<p>Mulai dari setengah ruang, impedansi di puncak tiap lapisan dihitung ke atas:</p>
[[EQ: $Z_j = Z_j^0\,\dfrac{Z_{j+1}+Z_j^0\tanh(k_jh_j)}{Z_j^0+Z_{j+1}\tanh(k_jh_j)}$]]
<p>Nilai di permukaan memberi ρ<sub>a</sub> dan φ.</p>
<h3>Transformasi Niblett–Bostick (pendekatan)</h3>
[[EQ: $D=\sqrt{\dfrac{\rho_a}{\omega\mu_0}},\qquad \rho_B=\rho_a\left(\dfrac{\pi}{2\varphi}-1\right)$]]
<p>Ditampilkan sebagai titik oranye pada plot model. Ini pendekatan cepat, bukan inversi.</p>
"""

TOPICS["Skin depth & sensitivitas"] = r"""
<h2>Skin depth</h2>
[[EQ: $\delta=\sqrt{\dfrac{2\rho}{\omega\mu_0}}\approx 503\sqrt{\dfrac{\rho}{f}}\ \ \mathrm{[m]}$]]
<p>δ adalah kedalaman tempat amplitudo gelombang bidang dalam medium <b>homogen</b> turun menjadi 1/e (37 %).</p>
<ul>
<li>Frekuensi lebih rendah → δ lebih besar → penetrasi lebih dalam.</li>
<li>Resistivitas lebih tinggi → δ lebih besar. Lapisan penutup konduktif "menyaring" lapisan di bawahnya.</li>
<li>Lapisan konduktif tipis terselesaikan melalui konduktansi S = h/ρ, lapisan resistif tipis melalui
T = hρ (ekuivalensi). Coba dengan inversi Marquardt.</li>
</ul>
<h3>Sensitivitas</h3>
[[EQ: $S_p(f) = \dfrac{\partial \ln\rho_a(f)}{\partial \ln p}$]]
<p>Pita frekuensi dengan |S<sub>p</sub>| besar adalah pita yang "melihat" lapisan itu. Inversi memakai
turunan ini (Jacobian).</p>
"""

TOPICS["Pemodelan kedepan 2D (TE / TM)"] = r"""
<h2>Bumi 2D: mode TE dan TM</h2>
<p>Untuk resistivitas ρ(y, z) yang konstan sepanjang jurus x, persamaan Maxwell terpisah menjadi dua polarisasi:</p>
[[EQ: $\mathrm{TE:}\ \ \dfrac{\partial^2E_x}{\partial y^2}+\dfrac{\partial^2E_x}{\partial z^2}=i\omega\mu_0\sigma E_x,\qquad H_y=-\dfrac{1}{i\omega\mu_0}\dfrac{\partial E_x}{\partial z}$]]
[[EQ: $\mathrm{TM:}\ \ \dfrac{\partial}{\partial y}\left(\rho\dfrac{\partial H_x}{\partial y}\right)+\dfrac{\partial}{\partial z}\left(\rho\dfrac{\partial H_x}{\partial z}\right)=i\omega\mu_0H_x,\qquad E_y=\rho\dfrac{\partial H_x}{\partial z}$]]
<ul>
<li><b>TE</b>: arus mengalir sejajar jurus; lapisan udara harus disertakan. Respons berubah halus melintasi
kontak; peka terhadap konduktor.</li>
<li><b>TM</b>: arus memotong struktur; muatan terkumpul di batas. Respons ρ<sub>a</sub> melompat tajam di kontak;
peka terhadap resistor dan batas lateral.</li>
</ul>
<h3>Metode numerik</h3>
<ul>
<li>Volume hingga berbasis node pada mesh tensor, stensil 5 titik, solver langsung sparse (SciPy).</li>
<li>Mesh dibangun ulang untuk tiap frekuensi: sel ≤ δ/10 di dekat permukaan, padding ≥ 5 skin depth.</li>
<li>Syarat batas Dirichlet dari solusi 1D kolom tepi.</li>
<li>Untuk model homogen lateral, hasil 2D sama dengan 1D (selisih ≈ 0,1 %, 0,15°).</li>
</ul>
"""

TOPICS["Noise, error, dan error floor"] = r"""
<h2>Noise dan error data</h2>
<p>Data nyata mengandung noise. Tab Noise &amp; Data menambahkan noise pada impedansi sintetik dan mencatat
error 1-σ yang ditulis ke berkas EDI (VAR = σ²) dan dipakai inversi.</p>
<ul><li><b>Gaussian pada Z</b>: Z<sub>obs</sub> = Z(1 + p·n). σ(ρa)/ρa ≈ √2·p, σ(φ) ≈ p/√2 rad.</li>
<li><b>Gaussian pada ρa dan φ</b>: noise terpisah pada ρa (%) dan fase (°).</li>
<li><b>Uniform</b>: noise terbatas ±p.</li>
<li><b>Pencilan (outlier)</b>: beberapa frekuensi mendapat error k× lebih besar yang <i>tidak</i> tercantum di σ.</li></ul>
<p><b>Error floor</b>: error terkecil yang diterima (mis. 5 % dari |Z|). Floor lebih besar → model lebih halus dan
RMS lebih kecil; floor terlalu kecil memaksa inversi mencocokkan noise.</p>
"""

TOPICS["Inversi 1D (Occam & Marquardt)"] = r"""
<h2>Inversi 1D</h2>
<p>Data d = [log10 ρa, φ]; misfit:</p>
[[EQ: $\mathrm{RMS}=\sqrt{\dfrac{1}{N}\sum_i\left(\dfrac{d_i^{obs}-d_i^{pred}}{\sigma_i}\right)^2}$]]
<p>RMS ≈ 1 berarti model menjelaskan data sesuai tingkat error-nya.</p>
<h3>Occam (halus)</h3>
[[EQ: $\min\ \|W(d-F(m))\|^2+\lambda\|Rm\|^2$]]
<p>Banyak lapisan tipis dengan kedalaman tetap; m = log10 ρ. λ dipilih sehingga model <b>paling halus</b> yang
mencapai RMS target yang dipakai. Hasilnya hanya menampilkan struktur yang benar-benar dituntut data.</p>
<h3>Marquardt (berlapis)</h3>
[[EQ: $(G^TG+\mu\,\mathrm{diag}(G^TG))\,\Delta m=G^TW\,r$]]
<p>Sedikit lapisan; parameter log ρ dan log h. Beberapa model awal dicoba dan yang terbaik dipakai. Faktor
ketidakpastian (×/÷) dan korelasi parameter memperlihatkan <b>ekuivalensi</b>: konduktor tipis terselesaikan
melalui S = h/ρ, resistor tipis melalui T = h·ρ.</p>
"""

TOPICS["Inversi 2D (Occam)"] = r"""
<h2>Inversi Occam 2D</h2>
<p>Model berupa grid blok (kolom di antara stasiun, lapisan berspasi logaritmik); m = log10 ρ tiap blok.
Jacobian dihitung dengan metode adjoint dari solver volume hingga. Setiap iterasi menyelesaikan</p>
[[EQ: $(G^TG+\lambda R^TR)\,m_{k+1}=G^TW\,(d-F(m_k)+Jm_k)$]]
<p>R berisi beda hingga horizontal (bobot α) dan vertikal. λ dipilih dari misfit terlinierkan; langkah hanya
diterima bila RMS sebenarnya turun. Gunakan sedikit frekuensi dan stasiun — ini versi untuk pembelajaran.</p>
"""

TOPICS["Batasan"] = r"""
<h2>Batasan</h2>
<ul>
<li>Hanya sumber gelombang bidang (tanpa CSAMT / medan dekat pemancar).</li>
<li>Kuasi-statis; isotropik; tanpa topografi; μ = μ₀.</li>
<li>Solver 2D tanpa keluaran tipper; tepi poligon mengikuti resolusi mesh.</li>
<li>Kedalaman Niblett–Bostick hanya pendekatan.</li>
<li>Inversi 2D adalah versi sederhana (grid kasar).</li>
</ul>
"""

EXPERIMENTS = [
    ("1. Setengah ruang: kasus acuan", "Ubah ρ dengan slider (10, 100, 1000 Ω·m).",
     "ρa sama dengan ρ di semua frekuensi dan fase tetap 45°. Hanya skin depth yang berubah."),
    ("2. Interpretasi interaktif: lempung konduktif", "Tekan 'Jadikan referensi', lalu ubah lapisan 2 dari 5 menjadi 50 Ω·m.",
     "Minimum ρa hilang dan fase di atas 45° turun. Panel interpretasi menunjukkan frekuensi yang paling berubah."),
    ("3. Ekuivalensi konduktor tipis (S = h/ρ)", "Jadikan referensi. Lalu atur lapisan 2: ρ = 5 Ω·m, h = 50 m (S tetap 10 S).",
     "Kedua kurva hampir identik: MT hanya menyelesaikan konduktansi konduktor tipis, bukan ρ dan h terpisah."),
    ("4. Lapisan resistif sulit terlihat", "Jadikan referensi, gandakan resistor menjadi 2000 Ω·m. Lalu gandakan ketebalannya.",
     "Mengubah ρ saja hampir tidak mengubah kurva; mengubah h·ρ (resistansi transversal) mengubahnya."),
    ("5. Pita frekuensi dan kedalaman", "Ganti metode antara AMT dan MT.",
     "AMT hanya melihat lapisan atas; pita MT mencapai batuan dasar."),
    ("6. VLF-R: satu frekuensi, penetrasi dangkal", "Ubah ketebalan tanah kering dari 5 menjadi 40 m.",
     "Pada ~20 kHz ρa/φ berubah kuat selama tanah lebih tipis dari ~1 skin depth, lalu berhenti berubah."),
    ("7. Noise dan inversi (alur lengkap)",
     "Noise & Data: Gaussian 5 %, ekspor EDI. Inversi 1D: muat EDI, jalankan Occam, lalu Marquardt (3 lapis).",
     "Occam memperoleh konduktor halus di sekitar 200–500 m; Marquardt memperoleh ρ dan h beserta ketidakpastian. "
     "Bandingkan keduanya dengan model sebenarnya."),
]
