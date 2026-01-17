const routeSelect = document.getElementById("route-filter");
const dateSelect = document.getElementById("date-filter");
const chartGrid = document.getElementById("chart-grid");
const chartStatus = document.getElementById("chart-status");

if (routeSelect && dateSelect && chartGrid) {
  const chartCards = Array.from(chartGrid.querySelectorAll(".chart-card"));
  const routes = new Set();
  const dates = new Set();

  chartCards.forEach((card) => {
    const route = card.dataset.route;
    if (route) {
      routes.add(route);
    }
    const date = card.dataset.date;
    if (date) {
      dates.add(date);
    }
  });

  const sortedRoutes = Array.from(routes).sort((a, b) =>
    a.localeCompare(b),
  );
  const sortedDates = Array.from(dates).sort((a, b) => a.localeCompare(b));

  const allOption = document.createElement("option");
  allOption.value = "all";
  allOption.textContent = "All routes";
  routeSelect.appendChild(allOption);

  sortedRoutes.forEach((route) => {
    const option = document.createElement("option");
    option.value = route;
    option.textContent = route;
    routeSelect.appendChild(option);
  });

  const allDatesOption = document.createElement("option");
  allDatesOption.value = "all";
  allDatesOption.textContent = "All dates";
  dateSelect.appendChild(allDatesOption);

  sortedDates.forEach((date) => {
    const option = document.createElement("option");
    option.value = date;
    option.textContent = date;
    dateSelect.appendChild(option);
  });

  const updateView = () => {
    const selectedRoute = routeSelect.value;
    const selectedDate = dateSelect.value;
    let visibleCount = 0;

    chartCards.forEach((card) => {
      const matches =
        (selectedRoute === "all" || card.dataset.route === selectedRoute) &&
        (selectedDate === "all" || card.dataset.date === selectedDate);
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

  routeSelect.addEventListener("change", updateView);
  dateSelect.addEventListener("change", updateView);
  updateView();
} else if (chartStatus) {
  chartStatus.textContent = "No charts available.";
}
