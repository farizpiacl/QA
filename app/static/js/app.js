// QA Portal PIA — global JS

document.addEventListener("DOMContentLoaded", function () {
  var body = document.body;
  var burger = document.getElementById("sidebarBurger");
  var desktopToggle = document.getElementById("sidebarDesktopToggle");
  var collapseBtn = document.getElementById("sidebarCollapseBtn");
  var backdrop = document.getElementById("sidebarBackdrop");
  var sidebar = document.getElementById("appSidebar");

  // --- Desktop collapse (icon-rail) state, persisted across pages ------
  var COLLAPSE_KEY = "qaPortalSidebarCollapsed";
  if (sidebar) {
    try {
      if (localStorage.getItem(COLLAPSE_KEY) === "1") {
        body.classList.add("sidebar-collapsed");
      }
    } catch (e) { /* localStorage unavailable — ignore */ }
  }

  function toggleDesktopCollapse() {
    body.classList.toggle("sidebar-collapsed");
    try {
      localStorage.setItem(COLLAPSE_KEY, body.classList.contains("sidebar-collapsed") ? "1" : "0");
    } catch (e) { /* ignore */ }
  }

  if (desktopToggle) desktopToggle.addEventListener("click", toggleDesktopCollapse);
  if (collapseBtn) collapseBtn.addEventListener("click", toggleDesktopCollapse);

  // --- Mobile / tablet off-canvas sidebar --------------------------------
  function openMobileSidebar() {
    body.classList.add("sidebar-mobile-open");
  }
  function closeMobileSidebar() {
    body.classList.remove("sidebar-mobile-open");
  }

  if (burger) burger.addEventListener("click", openMobileSidebar);
  if (backdrop) backdrop.addEventListener("click", closeMobileSidebar);

  // Close the mobile sidebar automatically after navigating.
  if (sidebar) {
    sidebar.querySelectorAll(".sidebar-link").forEach(function (link) {
      link.addEventListener("click", function () {
        if (window.innerWidth < 992) closeMobileSidebar();
      });
    });
  }

  // Close on Escape and when resizing back up to desktop.
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeMobileSidebar();
  });
  window.addEventListener("resize", function () {
    if (window.innerWidth >= 992) closeMobileSidebar();
  });

  // --- Auto-dismiss success alerts for a cleaner feel ---------------------
  document.querySelectorAll(".alert-success").forEach(function (el) {
    setTimeout(function () {
      if (window.bootstrap && window.bootstrap.Alert) {
        var alert = window.bootstrap.Alert.getOrCreateInstance(el);
        alert.close();
      }
    }, 5000);
  });
});
