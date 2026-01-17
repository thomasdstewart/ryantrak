const filterSelect = document.getElementById("route-filter");
const chartGrid = document.getElementById("chart-grid");
const chartStatus = document.getElementById("chart-status");

if (filterSelect && chartGrid) {
  const chartCards = Array.from(chartGrid.querySelectorAll(".chart-card"));
  const routes = new Set();

  chartCards.forEach((card) => {
    const route = card.dataset.route;
    if (route) {
      routes.add(route);
    }
  });

  const sortedRoutes = Array.from(routes).sort((a, b) =>
    a.localeCompare(b),
  );

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "All routes";
  filterSelect.appendChild(allOption);

  sortedRoutes.forEach((route) => {
    const option = document.createElement("option");
    option.value = route;
    option.textContent = route;
    filterSelect.appendChild(option);
  });

  const updateView = () => {
    const selectedRoute = filterSelect.value;
    let visibleCount = 0;

    chartCards.forEach((card) => {
      const matches =
        selectedRoute === "all" || card.dataset.route === selectedRoute;
      card.style.display = matches ? "flex" : "none";
      if (matches) {
        visibleCount += 1;
      }
    });

    if (chartStatus) {
      const total = chartCards.length;
      chartStatus.textContent = `${visibleCount} of ${total} charts shown`;
    }
  };

  filterSelect.addEventListener("change", updateView);
  updateView();
} else if (chartStatus) {
  chartStatus.textContent = "No charts available.";
}
