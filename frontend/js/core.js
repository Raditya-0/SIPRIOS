/*
   SIPRIOS — core.js
   Shell (sidebar/topbar), klien API backend, toast,
   loading overlay, modal, autentikasi berbasis token.
*/
(function () {
  "use strict";

  /* Konfigurasi API */
  var API_BASE = "https://siprios.my.id";

  /* Kunci penyimpanan sesi */
  var TOKEN_KEY = "siprios_token";
  var CUR_KEY = "siprios_current";
  var SELECTED_KEY = "siprios_selected";

  /* Helper fetch dengan guard 401/403 */
  function apiFetch(path, opts) {
    opts = opts || {};
    opts.headers = opts.headers || {};
    var token = sessionStorage.getItem(TOKEN_KEY);
    if (token) opts.headers["Authorization"] = "Bearer " + token;
    return fetch(API_BASE + path, opts).then(function (res) {
      if (res.status === 401) {
        Auth.logout();
        window.location.href = "/index.html";
        throw new Error("401 Unauthorized");
      }
      if (res.status === 403) {
        sessionStorage.setItem("lockReason", "Server menolak akses ke sumber daya ini.");
        window.location.href = "/pages/403.html";
        throw new Error("403 Forbidden");
      }
      return res;
    }, function () {
      throw new Error("Tidak dapat terhubung ke server. Periksa koneksi Anda.");
    });
  }

  /* Helper fetch + parse JSON, dengan pesan error manusiawi */
  function apiJSON(path, opts) {
    return apiFetch(path, opts).then(function (res) {
      return res.json().catch(function () { return {}; }).then(function (data) {
        if (!res.ok) {
          var msg = (data && data.detail) ? data.detail : "Terjadi kesalahan. Silakan coba lagi.";
          throw new Error(msg);
        }
        return data;
      });
    });
  }

  /* API: Warga */
  function listWarga(params) {
    var qs = "";
    if (params) {
      var parts = [];
      Object.keys(params).forEach(function (k) {
        var v = params[k];
        if (v !== undefined && v !== null && v !== "") {
          parts.push(encodeURIComponent(k) + "=" + encodeURIComponent(v));
        }
      });
      if (parts.length) qs = "?" + parts.join("&");
    }
    return apiJSON("/api/warga" + qs);
  }
  function getWarga(id) { return apiJSON("/api/warga/" + encodeURIComponent(id)); }
  function postWarga(formData) { return apiJSON("/api/warga", { method: "POST", body: formData }); }
  function putWarga(id, formData) { return apiJSON("/api/warga/" + encodeURIComponent(id), { method: "PUT", body: formData }); }
  function deleteWarga(id) { return apiJSON("/api/warga/" + encodeURIComponent(id), { method: "DELETE" }); }

  /* Unduh berkas export sebagai blob lalu trigger save */
  function downloadFile(path) {
    return apiFetch(path).then(function (res) {
      if (!res.ok) throw new Error("Gagal membuat berkas unduhan.");
      var cd = res.headers.get("Content-Disposition") || "";
      var m = cd.match(/filename="?([^"]+)"?/);
      var filename = m ? m[1] : "unduhan";
      return res.blob().then(function (blob) {
        var url = URL.createObjectURL(blob);
        var a = document.createElement("a");
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      });
    });
  }

  /* Penanda data warga yang dipilih (untuk navigasi ke profil) */
  var Store = {
    select: function (id) { sessionStorage.setItem(SELECTED_KEY, id); },
    selectedId: function () { return sessionStorage.getItem(SELECTED_KEY); },
    clearSelected: function () { sessionStorage.removeItem(SELECTED_KEY); }
  };

  /* Autentikasi & peran (berbasis token JWT)
     Peran: 'kepala_desa' (input data), 'admin' (kelola prioritas),
     tanpa login = 'warga' (hanya lihat dashboard & prioritas). */

  function roleLabel(role) {
    return role === "kepala_desa" ? "Kepala Desa" : role === "admin" ? "Admin" : "Pengguna";
  }

  var Auth = {
    current: function () {
      try { return JSON.parse(sessionStorage.getItem(CUR_KEY)) || null; }
      catch (e) { return null; }
    },
    token: function () { return sessionStorage.getItem(TOKEN_KEY); },

    login: function (username, password) {
      return fetch(API_BASE + "/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username: username, password: password })
      }).then(function (res) {
        return res.json().catch(function () { return {}; }).then(function (data) {
          if (!res.ok) return { error: data.detail || "Username atau kata sandi salah." };
          sessionStorage.setItem(TOKEN_KEY, data.token);
          sessionStorage.setItem(CUR_KEY, JSON.stringify(data.user));
          return { user: data.user };
        });
      }, function () {
        return { error: "Tidak dapat terhubung ke server. Periksa koneksi Anda." };
      });
    },

    // Registrasi hanya untuk Kepala Desa, dengan surat bukti (PDF). Menunggu ACC admin.
    register: function (nama, username, password, suratFile) {
      var fd = new FormData();
      fd.append("nama", nama);
      fd.append("username", username);
      fd.append("password", password);
      fd.append("surat", suratFile);
      return fetch(API_BASE + "/api/auth/register", { method: "POST", body: fd })
        .then(function (res) {
          return res.json().catch(function () { return {}; }).then(function (data) {
            if (!res.ok) return { error: data.detail || "Pendaftaran gagal. Silakan coba lagi." };
            return { pending: true };
          });
        }, function () {
          return { error: "Tidak dapat terhubung ke server. Periksa koneksi Anda." };
        });
    },

    logout: function () {
      var token = sessionStorage.getItem(TOKEN_KEY);
      sessionStorage.removeItem(TOKEN_KEY);
      sessionStorage.removeItem(CUR_KEY);
      if (token) {
        fetch(API_BASE + "/api/auth/logout", {
          method: "POST",
          headers: { "Authorization": "Bearer " + token }
        }).catch(function () {});
      }
    },

    hasRole: function (roles) {
      var c = Auth.current(); if (!c) return false;
      if (Array.isArray(roles)) return roles.indexOf(c.role) !== -1;
      return c.role === roles;
    },
    isAdmin: function () { return Auth.hasRole("admin"); },
    isKepalaDesa: function () { return Auth.hasRole("kepala_desa"); },

    // Persetujuan akun (admin)
    pending: function () { return apiJSON("/api/akun/pending"); },
    approve: function (username) { return apiJSON("/api/akun/" + encodeURIComponent(username) + "/approve", { method: "POST" }); },
    reject: function (username) { return apiJSON("/api/akun/" + encodeURIComponent(username), { method: "DELETE" }); },

    roleLabel: roleLabel
  };

  /* Format */
  function rupiah(n) {
    if (n === null || n === undefined || n === "" || isNaN(n)) return "Rp 0";
    return "Rp " + Number(n).toLocaleString("id-ID");
  }
  function tanggalID(iso) {
    var bln = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"];
    var d = new Date(iso);
    return d.getDate() + " " + bln[d.getMonth()] + " " + d.getFullYear();
  }
  function initials(nama) {
    return nama.trim().split(/\s+/).slice(0, 2).map(function (s) { return s[0]; }).join("").toUpperCase();
  }

  /* Shell: sidebar + topbar */
  var NAV = [
    { href: "/index.html", icon: "fa-house", label: "Dashboard" },
    { href: "/pages/input.html", icon: "fa-pen-to-square", label: "Input Data Warga" },
    { href: "/pages/prioritas.html", icon: "fa-list-ol", label: "Daftar Prioritas" },
    { href: "/pages/approval.html", icon: "fa-user-check", label: "Persetujuan Akun" }
  ];

  function renderShell(opts) {
    var active = opts.active;
    var user = Auth.current();

    function navVisible(href) {
      if (href === "/pages/input.html") return !!user && user.role === "kepala_desa";
      if (href === "/pages/approval.html") return !!user && user.role === "admin";
      return true; // Dashboard & Daftar Prioritas terbuka untuk warga (tanpa login)
    }

    var navHtml = NAV.filter(function (n) { return navVisible(n.href); }).map(function (n) {
      var cls = "topnav__link" + (n.href === active ? " is-active" : "");
      var badge = (n.href === "/pages/approval.html") ? ' <span class="nav-badge" id="approvalBadge" style="display:none;"></span>' : '';
      return '<a class="' + cls + '" href="' + n.href + '"><span class="nav__icon"><i class="fa-solid ' + n.icon + ' nav-icon"></i></span><span>' + n.label + badge + '</span></a>';
    }).join("");

    var right;
    if (user) {
      right =
        '<div class="topbar__user"><div class="ava">' + initials(user.nama) + '</div>' +
          '<div class="meta"><b>' + user.nama + '</b><span>' + roleLabel(user.role) + '</span></div></div>' +
        '<button class="btn btn--ghost" id="logoutBtn"><i class="fa-solid fa-right-from-bracket btn-icon"></i>Keluar</button>';
    } else {
      // Pengunjung tanpa login: cukup tombol Masuk (tanpa label "Mode Warga")
      right = '<button class="btn btn--primary" id="loginBtn" style="font-size:14px;height:38px;padding:0 20px;"><i class="fa-solid fa-arrow-right-to-bracket btn-icon"></i>Masuk</button>';
    }

    var nav =
      '<header class="topnav">' +
        '<a class="topnav__brand" href="/index.html">' +
          '<span class="brand__mark"><i class="fa-solid fa-bowl-food" style="font-size:24px;color:inherit;"></i></span>' +
          '<span class="brand__text"><span class="brand__name">SIPRIOS</span><span class="brand__sub">Sistem Prioritas Sosial</span></span>' +
        '</a>' +
        '<nav class="topnav__nav" id="sipriosNav">' + navHtml + '</nav>' +
        '<div class="topnav__right">' + right +
          '<button class="nav-burger" id="sipriosBurger" aria-label="Buka menu"><i class="fa-solid fa-bars"></i></button>' +
        '</div>' +
      '</header>';

    document.getElementById("shell-sidebar").innerHTML = nav;
    document.getElementById("shell-topbar").innerHTML = "";

    // Menu mobile
    var burger = document.getElementById("sipriosBurger");
    var menu = document.getElementById("sipriosNav");
    burger.addEventListener("click", function () { menu.classList.toggle("is-open"); });

    // Masuk / Logout
    if (user) {
      document.getElementById("logoutBtn").addEventListener("click", function () {
        openConfirm("Keluar dari Akun", "Anda akan keluar dari akun dan kembali sebagai pengunjung biasa. Lanjutkan?", function () {
          Auth.logout();
          toast("Anda telah keluar.", "info");
          setTimeout(function () { window.location.href = "/index.html"; }, 500);
        });
      });
    } else {
      document.getElementById("loginBtn").addEventListener("click", function () { openAuthModal("login"); });
    }

    // Lencana jumlah permohonan tertunda (admin)
    if (user && user.role === "admin") {
      Auth.pending().then(function (list) {
        var badgeEl = document.getElementById("approvalBadge");
        if (badgeEl && list && list.length > 0) {
          badgeEl.textContent = list.length;
          badgeEl.style.display = "inline";
        }
      }).catch(function () { /* badge bersifat opsional */ });
    }

    // Penjaga akses berbasis peran (untuk halaman yang butuh login/role)
    if (opts.requireRole) {
      var perlu = opts.requireRole === "kepala_desa" ? "Kepala Desa" : "Admin";
      if (!user) {
        lockScreen("Masuk Diperlukan",
          "Halaman ini memerlukan akun " + perlu + ". Silakan masuk untuk melanjutkan.", true);
        return false;
      }
      if (!Auth.hasRole(opts.requireRole)) {
        lockScreen("Akses Terbatas",
          "Halaman ini khusus untuk " + perlu + ". Anda masuk sebagai " + roleLabel(user.role) + ".", false);
        return false;
      }
    }
    return true;
  }

  /* Modal Masuk / Daftar Kepala Desa */
  function openAuthModal(tab) {
    var root = openModal(
      '<button class="close" data-close><i class="fa-solid fa-xmark"></i></button>' +
        '<div class="auth-head"><span class="brand__mark"><i class="fa-solid fa-bowl-food" style="font-size:24px;color:inherit;"></i></span><div style="min-width:0;"><h3 style="margin:0;white-space:nowrap;">Masuk ke SIPRIOS</h3><p style="margin:2px 0 0;font-size:13px;color:var(--color-muted);">Sistem Prioritas Sosial — Kota Surabaya</p></div></div>' +
        '<div class="auth-tabs"><button type="button" class="auth-tab" data-tab="login">Masuk</button><button type="button" class="auth-tab" data-tab="register">Daftar Kepala Desa</button></div>' +
        '<form id="paneLogin" class="auth-pane">' +
          '<div class="field"><label>Username</label><input type="text" id="lgUser" placeholder="masukkan username" autocomplete="username"></div>' +
          '<div class="field"><label>Kata Sandi</label><input type="password" id="lgPass" placeholder="masukkan kata sandi" autocomplete="current-password"></div>' +
          '<button type="submit" class="btn btn--primary btn--block btn--lg">Masuk</button>' +
        '</form>' +
        '<form id="paneRegister" class="auth-pane" hidden>' +
          '<div class="callout"><span class="ic"><i class="fa-solid fa-circle-info"></i></span><div>Pendaftaran <b>khusus Kepala Desa</b>. Akun ditinjau & disetujui admin sebelum dapat digunakan. Admin tidak mendaftar di sini.</div></div>' +
          '<div class="field"><label>Nama Lengkap <span class="req">*</span></label><input type="text" id="rgNama" placeholder="contoh: Budi Santoso"></div>' +
          '<div class="field"><label>Username <span class="req">*</span></label><input type="text" id="rgUser" placeholder="pilih username"></div>' +
          '<div class="field"><label>Kata Sandi <span class="req">*</span></label><input type="password" id="rgPass" placeholder="minimal 6 karakter"></div>' +
          '<div class="field"><label>Surat Keterangan Kepala Desa (PDF) <span class="req">*</span></label>' +
            '<label class="upload" for="rgSurat" id="rgSuratBox" style="padding:18px;"><div class="ic"><i class="fa-solid fa-file-pdf"></i></div><p>Klik untuk unggah surat bukti &middot; PDF &middot; maks 5MB</p></label>' +
            '<input type="file" id="rgSurat" accept="application/pdf,.pdf" hidden>' +
            '<div id="rgSuratInfo" style="display:none;align-items:center;gap:10px;margin-top:8px;font-size:14px;"><span style="font-weight:700;color:var(--color-success);"><i class="fa-solid fa-check"></i></span><span id="rgSuratName"></span><button type="button" id="rgSuratDel" class="btn btn--ghost" style="min-height:auto;padding:4px 10px;margin-left:auto;">Ganti</button></div>' +
            '<span class="helper">Surat keterangan dari kecamatan sebagai bukti jabatan Kepala Desa.</span>' +
          '</div>' +
          '<button type="submit" class="btn btn--primary btn--block btn--lg">Kirim Pendaftaran</button>' +
        '</form>'
    , true);
    root.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", closeModal); });

    function setTab(t) {
      root.querySelectorAll(".auth-tab").forEach(function (b) { b.classList.toggle("is-active", b.getAttribute("data-tab") === t); });
      root.querySelector("#paneLogin").hidden = (t !== "login");
      root.querySelector("#paneRegister").hidden = (t !== "register");
    }
    root.querySelectorAll(".auth-tab").forEach(function (b) { b.addEventListener("click", function () { setTab(b.getAttribute("data-tab")); }); });
    setTab(tab || "login");

    // Unggah surat PDF
    var suratFile = null;
    var fileInput = root.querySelector("#rgSurat");
    fileInput.addEventListener("change", function () {
      var f = fileInput.files[0]; if (!f) return;
      if (f.type !== "application/pdf" && !/\.pdf$/i.test(f.name)) { toast("Surat harus berformat PDF.", "error"); fileInput.value = ""; return; }
      if (f.size > 5 * 1024 * 1024) { toast("Ukuran PDF maksimal 5MB.", "error"); fileInput.value = ""; return; }
      suratFile = f;
      root.querySelector("#rgSuratName").textContent = f.name;
      root.querySelector("#rgSuratInfo").style.display = "flex";
      root.querySelector("#rgSuratBox").style.display = "none";
    });
    root.querySelector("#rgSuratDel").addEventListener("click", function () {
      suratFile = null; fileInput.value = "";
      root.querySelector("#rgSuratInfo").style.display = "none";
      root.querySelector("#rgSuratBox").style.display = "block";
    });

    // Submit masuk
    root.querySelector("#paneLogin").addEventListener("submit", function (e) {
      e.preventDefault();
      var u = root.querySelector("#lgUser").value.trim(), p = root.querySelector("#lgPass").value;
      if (!u || !p) { toast("Lengkapi username dan kata sandi.", "error"); return; }
      overlay(true, "Memeriksa akun...");
      Auth.login(u, p).then(function (res) {
        overlay(false);
        if (res.error) { toast(res.error, "error"); return; }
        toast("Selamat datang, " + res.user.nama + "!", "success");
        setTimeout(function () { window.location.reload(); }, 500);
      });
    });

    // Submit daftar (Kepala Desa, menunggu ACC admin)
    root.querySelector("#paneRegister").addEventListener("submit", function (e) {
      e.preventDefault();
      var nama = root.querySelector("#rgNama").value.trim();
      var u = root.querySelector("#rgUser").value.trim();
      var p = root.querySelector("#rgPass").value;
      if (nama.length < 3) { toast("Nama minimal 3 karakter.", "error"); return; }
      if (u.length < 3) { toast("Username minimal 3 karakter.", "error"); return; }
      if (p.length < 6) { toast("Kata sandi minimal 6 karakter.", "error"); return; }
      if (!suratFile) { toast("Wajib unggah surat keterangan (PDF).", "error"); return; }
      overlay(true, "Mengirim pendaftaran...");
      Auth.register(nama, u, p, suratFile).then(function (res) {
        overlay(false);
        if (res.error) { toast(res.error, "error"); return; }
        root.querySelector(".modal").innerHTML =
          '<button class="close" data-close><i class="fa-solid fa-xmark"></i></button>' +
          '<div class="empty" style="padding:24px 8px 8px;"><div class="ic empty-icon"><i class="fa-solid fa-hourglass-half"></i></div>' +
          '<h3>Pendaftaran Terkirim</h3>' +
          '<p>Terima kasih, <b>' + nama + '</b>. Pendaftaran Anda sebagai Kepala Desa sedang <b>menunggu persetujuan admin</b>. Anda dapat masuk setelah akun disetujui.</p>' +
          '<button class="btn btn--primary" id="backToLogin">Mengerti</button></div>';
        root.querySelector("[data-close]").addEventListener("click", closeModal);
        root.querySelector("#backToLogin").addEventListener("click", function () { closeModal(); });
      });
    });
  }

  /* Layar terkunci → redirect ke 403.html */
  function lockScreen(title, msg, showLogin) {
    sessionStorage.setItem("lockReason", msg || title || "Halaman ini tidak dapat diakses dengan peran Anda saat ini.");
    window.location.href = "403.html";
  }

  /* Toast */
  function ensureToastStack() {
    var el = document.getElementById("toastStack");
    if (!el) { el = document.createElement("div"); el.id = "toastStack"; el.className = "toast-stack"; document.body.appendChild(el); }
    return el;
  }
  function toast(msg, type) {
    type = type || "info";
    var icons = { success: "fa-circle-check", error: "fa-circle-xmark", info: "fa-circle-info" };
    var stack = ensureToastStack();
    var t = document.createElement("div");
    t.className = "toast " + type;
    t.innerHTML = '<span class="ic toast-icon"><i class="fa-solid ' + (icons[type] || icons.info) + '"></i></span><span>' + msg + '</span>';
    stack.appendChild(t);
    setTimeout(function () { t.style.transition = "opacity .24s, transform .24s"; t.style.opacity = "0"; t.style.transform = "translateX(120%)"; setTimeout(function () { t.remove(); }, 240); }, 4000);
  }

  /* Loading overlay */
  function overlay(on, text) {
    var el = document.getElementById("sipriosOverlay");
    if (!el) {
      el = document.createElement("div");
      el.id = "sipriosOverlay"; el.className = "overlay";
      el.innerHTML = '<div class="spinner"></div><div class="ot" id="sipriosOverlayText">Memproses data...</div>';
      document.body.appendChild(el);
    }
    if (text) document.getElementById("sipriosOverlayText").textContent = text;
    el.classList.toggle("is-on", !!on);
  }

  /* Modal generik */
  function openModal(html, noDismiss) {
    var bd = document.getElementById("sipriosModal");
    if (!bd) {
      bd = document.createElement("div"); bd.id = "sipriosModal"; bd.className = "modal-backdrop";
      document.body.appendChild(bd);
      bd.addEventListener("click", function (e) { if (e.target === bd && !bd.dataset.noDismiss) closeModal(); });
    }
    bd.dataset.noDismiss = noDismiss ? "1" : "";
    bd.innerHTML = '<div class="modal" role="dialog" aria-modal="true">' + html + '</div>';
    bd.classList.add("is-on");
    return bd;
  }
  function closeModal() {
    var bd = document.getElementById("sipriosModal");
    if (bd) bd.classList.remove("is-on");
  }

  function openConfirm(title, body, onYes) {
    var bd = openModal(
      '<button class="close" data-close><i class="fa-solid fa-xmark"></i></button>' +
      '<h3>' + title + '</h3>' +
      '<p style="font-size:14px;color:var(--color-muted);margin:0 0 24px;">' + body + '</p>' +
      '<div style="display:flex;gap:12px;">' +
        '<button class="btn btn--ghost btn--block" data-close>Batal</button>' +
        '<button class="btn btn--primary btn--block" id="confirmYes">Ya, Lanjutkan</button>' +
      '</div>'
    );
    bd.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", closeModal); });
    bd.querySelector("#confirmYes").addEventListener("click", function () { closeModal(); onYes && onYes(); });
  }

  // Modal form sederhana (lapor / masukan)
  function openFormModal(title, placeholder, onSubmit) {
    var bd = openModal(
      '<button class="close" data-close><i class="fa-solid fa-xmark"></i></button>' +
      '<h3>' + title + '</h3>' +
      '<div class="field" style="margin-bottom:20px;"><label for="mf">Keterangan</label>' +
      '<textarea id="mf" placeholder="' + placeholder + '"></textarea></div>' +
      '<button class="btn btn--primary btn--block btn--lg" id="mfSubmit">Kirim</button>'
    );
    bd.querySelectorAll("[data-close]").forEach(function (b) { b.addEventListener("click", closeModal); });
    bd.querySelector("#mfSubmit").addEventListener("click", function () {
      var v = bd.querySelector("#mf").value.trim();
      if (!v) { toast("Mohon isi keterangan terlebih dahulu.", "error"); return; }
      closeModal();
      onSubmit && onSubmit(v);
    });
  }

  /* Ekspor global */
  window.SIPRIOS = {
    API_BASE: API_BASE,
    Store: Store,
    Auth: Auth,
    openAuthModal: openAuthModal,
    apiFetch: apiFetch,
    apiJSON: apiJSON,
    listWarga: listWarga,
    getWarga: getWarga,
    postWarga: postWarga,
    putWarga: putWarga,
    deleteWarga: deleteWarga,
    downloadFile: downloadFile,
    rupiah: rupiah,
    tanggalID: tanggalID,
    initials: initials,
    renderShell: renderShell,
    toast: toast,
    overlay: overlay,
    openModal: openModal,
    closeModal: closeModal,
    openConfirm: openConfirm,
    openFormModal: openFormModal
  };
})();
