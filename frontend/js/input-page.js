/* 
   SIPRIOS — input-page.js
   Mendukung dua mode:
   - Mode Tambah (default): form kosong, POST /api/warga
   - Mode Edit (?mode=edit&id=X): pre-fill form, PUT /api/warga/:id
*/
(function () {
  "use strict";
  var S = window.SIPRIOS;
  if (!S.renderShell({ active: "/pages/input.html", requireRole: "kepala_desa" })) return;

  /* Deteksi mode */
  var params = new URLSearchParams(location.search);
  var isEdit = params.get("mode") === "edit";
  var editId = params.get("id") || sessionStorage.getItem("editTargetId") || null;

  /* Set judul & label dinamis */
  if (isEdit) {
    document.title = "SIPRIOS \u2014 Edit Data Warga";
    var t = document.getElementById("pageTitle"); if (t) t.textContent = "Edit Data Warga";
    var d = document.getElementById("pageDesc"); if (d) d.textContent = "Perbarui data rumah tangga warga. Nomor KK tidak dapat diubah.";
    var bl = document.getElementById("breadcrumbLabel"); if (bl) bl.textContent = "Edit Data Warga";
    var sb = document.querySelector("#wargaForm .btn--primary.btn--block.btn--lg"); if (sb) sb.textContent = "Simpan Perubahan";
  }

  var form = document.getElementById("wargaForm");
  var fotoData = null;
  var fotoFile = null;
  var fotoFileName = "";
  var fotoKepaDariServer = null; // URL foto lama (mode edit)

  var REQUIRED = ["nomorKK", "nama", "totalAnggota", "jumlahDewasa", "jumlahAnak",
    "jumlahLansia", "jumlahRuangan", "kamarTidur", "statusToilet", "statusRumah", "rataSekolah"];
  document.getElementById("progText").textContent = "0/" + REQUIRED.length;

  /* Yes/No & radio pill */
  form.querySelectorAll("[data-pill]").forEach(function (row) {
    row.querySelectorAll(".pill").forEach(function (pill) {
      var input = pill.querySelector("input");
      input.addEventListener("change", function () {
        row.querySelectorAll(".pill").forEach(function (p) { p.classList.remove("is-checked"); });
        pill.classList.add("is-checked");
        clearError(row.getAttribute("data-pill"));
        refresh();
      });
    });
  });

  /* Stepper */
  form.querySelectorAll(".stepper").forEach(function (st) {
    var input = st.querySelector("input");
    st.querySelectorAll("button[data-step]").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var step = parseInt(btn.getAttribute("data-step"), 10);
        var min = input.min !== "" ? parseInt(input.min, 10) : 0;
        var cur = input.value === "" ? (step > 0 ? min - step : min) : parseInt(input.value, 10);
        var next = Math.max(min, cur + step);
        input.value = next;
        clearError(input.name);
        refresh();
      });
    });
    input.addEventListener("input", function () { clearError(input.name); refresh(); });
  });

  /* Text/number inputs */
  ["nomorKK", "nama", "sewaBulanan", "rataSekolah"].forEach(function (id) {
    var el = document.getElementById(id);
    el.addEventListener("input", function () { clearError(id); refresh(); });
    el.addEventListener("blur", function () { validateOne(id); });
  });

  /* Foto upload */
  var fotoInput = document.getElementById("foto");
  fotoInput.addEventListener("change", function () {
    var file = fotoInput.files[0];
    if (!file) return;
    if (!/image\/(jpeg|png|webp)/.test(file.type)) { S.toast("Format foto harus JPG, PNG, atau WebP.", "error"); fotoInput.value = ""; return; }
    if (file.size > 5 * 1024 * 1024) { S.toast("Foto terlalu besar. Maksimal 5MB.", "error"); fotoInput.value = ""; return; }
    fotoFile = file;
    var reader = new FileReader();
    reader.onload = function (e) {
      fotoData = e.target.result;
      fotoFileName = file.name;
      document.getElementById("fotoImg").src = fotoData;
      document.getElementById("fotoName").textContent = file.name;
      document.getElementById("fotoPreview").style.display = "flex";
      document.getElementById("uploadBox").style.display = "none";
      refresh();
    };
    reader.readAsDataURL(file);
  });
  document.getElementById("fotoRemove").addEventListener("click", function () {
    fotoData = null; fotoFile = null; fotoFileName = ""; fotoInput.value = ""; fotoKepaDariServer = null;
    document.getElementById("fotoPreview").style.display = "none";
    document.getElementById("uploadBox").style.display = "block";
    if (isEdit) { var up = document.getElementById("uploadBox"); if (up) { var p = up.querySelector("p"); if (p) p.textContent = "Klik untuk ganti foto \u00b7 JPG, PNG, WebP \u00b7 maks 5MB"; } }
    refresh();
  });

  /* Helpers */
  function val(name) {
    var el = form.elements[name];
    if (!el) return "";
    if (el.length && el[0] && el[0].type === "radio") {
      var checked = form.querySelector('[name="' + name + '"]:checked');
      return checked ? checked.value : "";
    }
    return el.value.trim();
  }
  function num(name) { var v = val(name); return v === "" ? null : Number(v); }
  function fieldEl(name) { return form.querySelector('[data-field="' + name + '"]'); }
  /* Set error, opsional ganti teks pesan */
  function setError(name, msg) {
    var f = fieldEl(name);
    if (!f) return;
    f.classList.add("is-error");
    if (msg) {
      var em = f.querySelector(".err-msg");
      if (em) em.textContent = msg;
    }
  }
  function clearError(name) { var f = fieldEl(name); if (f) f.classList.remove("is-error"); }

  var NOMOR_KK_MSG_LEN = "Nomor KK harus tepat 16 digit angka";
  var NOMOR_KK_MSG_DIGIT = "Nomor KK hanya boleh mengandung angka.";

  function isFilled(name) {
    var v = val(name);
    if (name === "nama") return v.length >= 3;
    if (name === "nomorKK") return /^\d{16}$/.test(v);
    if (name === "totalAnggota" || name === "jumlahDewasa" || name === "jumlahRuangan") return v !== "" && Number(v) >= 1;
    if (name === "rataSekolah") return v !== "" && Number(v) >= 0 && Number(v) <= 20;
    return v !== "";
  }

  /* Validasi nomor KK dengan pesan beda per kasus */
  function validateNomorKK() {
    var v = val("nomorKK");
    if (v === "") { setError("nomorKK", NOMOR_KK_MSG_LEN); return false; }
    if (!/^\d+$/.test(v)) { setError("nomorKK", NOMOR_KK_MSG_DIGIT); return false; }
    if (v.length !== 16) { setError("nomorKK", NOMOR_KK_MSG_LEN); return false; }
    clearError("nomorKK"); return true;
  }

  function validateOne(name) {
    if (REQUIRED.indexOf(name) === -1) return true;
    if (name === "nomorKK") return validateNomorKK();
    if (isFilled(name)) { clearError(name); return true; }
    setError(name); return false;
  }

  /* Pre-fill form (mode edit) */
  function setPill(name, value) {
    var row = form.querySelector('[data-pill="' + name + '"]');
    if (!row) return;
    row.querySelectorAll(".pill").forEach(function (p) {
      var inp = p.querySelector("input");
      if (inp && inp.value === value) {
        row.querySelectorAll(".pill").forEach(function (x) { x.classList.remove("is-checked"); });
        p.classList.add("is-checked");
        inp.checked = true;
      }
    });
  }

  function prefillForm(data) {
    // Text / number fields
    ["nomorKK", "nama", "sewaBulanan", "totalAnggota", "jumlahDewasa",
      "jumlahAnak", "jumlahLansia", "jumlahRuangan", "kamarTidur", "rataSekolah"].forEach(function (k) {
      var el = document.getElementById(k);
      if (el && data[k] !== undefined && data[k] !== null) el.value = data[k];
    });
    // Pills (Ya/Tidak)
    ["punyaKulkas", "punyaKamarMandi", "airBersih", "adaListrik", "punyaPlafon",
      "punyaDapur", "adaTidakSekolah", "adaPendidikanTinggi"].forEach(function (k) {
      if (data[k] !== undefined) setPill(k, data[k]);
    });
    // Pills multi-value (toilet, rumah)
    if (data.statusToilet) setPill("statusToilet", data.statusToilet);
    if (data.statusRumah) setPill("statusRumah", data.statusRumah);

    // Nomor KK readonly di mode edit
    var kkEl = document.getElementById("nomorKK");
    if (kkEl) { kkEl.readOnly = true; kkEl.style.background = "var(--color-bg)"; kkEl.style.color = "var(--color-muted)"; }

    // Foto lama
    if (data.fotoUrl) {
      var src = data.fotoUrl;
      fotoKepaDariServer = src; fotoData = src;
      document.getElementById("fotoImg").src = src;
      document.getElementById("fotoName").textContent = data.fotoNama || "Foto kondisi rumah";
      document.getElementById("fotoPreview").style.display = "flex";
      document.getElementById("uploadBox").style.display = "none";
      var up = document.getElementById("uploadBox"); if (up) { var p = up.querySelector("p"); if (p) p.textContent = "Klik untuk ganti foto \u00b7 JPG, PNG, WebP \u00b7 maks 5MB"; }
    }

    refresh();
  }

  /* Ringkasan & progress (realtime) */
  function refresh() {
    var nama = val("nama"), kk = val("nomorKK");
    document.getElementById("sumNama").textContent = nama || "\u2014";
    document.getElementById("sumKK").textContent = kk || "\u2014";
    var total = num("totalAnggota");
    document.getElementById("sumTotal").textContent = total ? (total + " orang") : "\u2014";
    var dw = num("jumlahDewasa") || 0, an = num("jumlahAnak") || 0, ln = num("jumlahLansia") || 0;
    document.getElementById("sumKomposisi").textContent = (dw || an || ln) ? (dw + " dewasa \u00b7 " + an + " anak \u00b7 " + ln + " lansia") : "\u2014";
    [["punyaKamarMandi"], ["airBersih"], ["adaListrik"], ["punyaPlafon"], ["punyaDapur"]].forEach(function (u) {
      var mark = document.querySelector('.mark[data-u="' + u[0] + '"]');
      if (!mark) return;
      var yes = val(u[0]) === "Ya";
      mark.className = "mark " + (yes ? "yes" : "no");
      mark.innerHTML = yes ? '<i class="fa-solid fa-check"></i>' : '<i class="fa-solid fa-xmark"></i>';
    });
    var fw = document.getElementById("sumFotoWrap");
    if (fotoData) { fw.style.display = "block"; document.getElementById("sumFoto").src = fotoData; }
    else { fw.style.display = "none"; }
    var done = REQUIRED.filter(isFilled).length;
    document.getElementById("progText").textContent = done + "/" + REQUIRED.length;
    document.getElementById("progFill").style.width = Math.round((done / REQUIRED.length) * 100) + "%";
  }

  /* Load data warga untuk mode edit */
  if (isEdit && editId) {
    S.overlay(true, "Memuat data...");
    S.getWarga(editId).then(function (wargaData) {
      S.overlay(false);
      prefillForm(wargaData);
    }).catch(function (err) {
      S.overlay(false);
      S.toast(err.message || "Data warga tidak ditemukan.", "error");
      setTimeout(function () { window.location.href = "prioritas.html"; }, 1200);
    });
  }

  /* Submit */
  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var firstBad = null;
    REQUIRED.forEach(function (name) {
      if (!validateOne(name)) { if (!firstBad) firstBad = name; }
    });
    if (firstBad) {
      S.toast("Lengkapi data wajib yang ditandai merah.", "error");
      var el = fieldEl(firstBad);
      if (el) { var y = el.getBoundingClientRect().top + window.scrollY - 120; window.scrollTo({ top: y, behavior: "smooth" }); }
      return;
    }

    S.overlay(true, isEdit ? "Memperbarui data..." : "Memproses data...");

    var fd = new FormData();
    if (!isEdit) fd.append("nomorKK", val("nomorKK"));
    fd.append("nama", val("nama"));
    fd.append("sewaBulanan", String(num("sewaBulanan") || 0));
    fd.append("punyaKulkas", val("punyaKulkas") || "Tidak");
    fd.append("totalAnggota", String(num("totalAnggota")));
    fd.append("jumlahDewasa", String(num("jumlahDewasa")));
    fd.append("jumlahAnak", String(num("jumlahAnak")));
    fd.append("jumlahLansia", String(num("jumlahLansia")));
    fd.append("jumlahRuangan", String(num("jumlahRuangan")));
    fd.append("kamarTidur", String(num("kamarTidur")));
    fd.append("punyaKamarMandi", val("punyaKamarMandi") || "Tidak");
    fd.append("airBersih", val("airBersih") || "Tidak");
    fd.append("adaListrik", val("adaListrik") || "Tidak");
    fd.append("punyaPlafon", val("punyaPlafon") || "Tidak");
    fd.append("punyaDapur", val("punyaDapur") || "Tidak");
    fd.append("statusToilet", val("statusToilet"));
    fd.append("statusRumah", val("statusRumah"));
    fd.append("rataSekolah", String(num("rataSekolah")));
    fd.append("adaTidakSekolah", val("adaTidakSekolah") || "Tidak");
    fd.append("adaPendidikanTinggi", val("adaPendidikanTinggi") || "Tidak");
    if (fotoFile) fd.append("foto", fotoFile);

    var nama = val("nama");
    var req = (isEdit && editId) ? S.putWarga(editId, fd) : S.postWarga(fd);
    req.then(function (result) {
      S.overlay(false);
      if (isEdit && editId) {
        S.Store.select(editId);
        sessionStorage.removeItem("editTargetId");
        S.toast("Data " + nama + " berhasil diperbarui.", "success");
        setTimeout(function () { window.location.href = "profil.html"; }, 700);
      } else {
        S.Store.select(result.id);
        S.toast("Data " + nama + " berhasil disimpan dan dinilai.", "success");
        setTimeout(function () { window.location.href = "prioritas.html"; }, 700);
      }
    }).catch(function (err) {
      S.overlay(false);
      S.toast(err.message || "Gagal menyimpan data. Silakan coba lagi.", "error");
    });
  });

  refresh();
})();
