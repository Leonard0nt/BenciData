const palette = [
  "#0ea5e9",
  "#22c55e",
  "#f97316",
  "#8b5cf6",
  "#06b6d4",
  "#f59e0b",
  "#e11d48",
  "#475569",
];

function formatNumber(value) {
  if (value === null || value === undefined) return 0;

  // Si ya es número, devolver tal cual
  if (typeof value === "number") {
    return value;
  }

  if (typeof value === "string") {
    const hasComma = value.includes(",");
    const hasDot = value.includes(".");

    // Caso 1: tiene punto y coma -> "60.000,00"
    if (hasComma && hasDot) {
      value = value.replace(/\./g, "");   // quitar miles
      value = value.replace(/,/g, ".");   // coma -> punto decimal
    }
    // Caso 2: solo coma -> "60000,00"
    else if (hasComma && !hasDot) {
      value = value.replace(/,/g, ".");   // coma -> punto decimal
    }
    // Caso 3: solo punto o nada -> "60000.00" o "60000"
    // no tocamos el punto, solo limpiamos espacios
    else {
      value = value.replace(/\s/g, "");
    }
  }

  const num = Number(value);
  return Number.isNaN(num) ? 0 : num;
}


function buildChartConfig(branch, colorOffset) {
  const labels = branch.inventories.map((inventory) => inventory.fuel_type);
  const capacities = branch.inventories.map((inventory) =>
    formatNumber(inventory.capacity),
  );
  const liters = branch.inventories.map((inventory) =>
    formatNumber(inventory.liters),
  );
  const remaining = capacities.map((capacity, index) =>
    Math.max(capacity - liters[index], 0),
  );

  const baseColor = palette[colorOffset % palette.length];
  const secondaryColor = `${baseColor}33`;

  // Para escalar bien el eje Y según la mayor capacidad
  const maxCapacity = Math.max(...capacities, 0);

  return {
    type: "bar",
    data: {
      labels,
      datasets: [
        {
          label: "Litros actuales (L)",
          data: liters,
          backgroundColor: baseColor,
          borderRadius: 8,
          maxBarThickness: 48,
          stack: "capacity", // 👈 misma pila
        },
        {
          label: "Capacidad restante (L)",
          data: remaining,
          backgroundColor: secondaryColor,
          borderRadius: 8,
          maxBarThickness: 48,
          stack: "capacity", // 👈 misma pila
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          callbacks: {
            label(context) {
              const label = context.dataset.label || "";
              const value = context.parsed.y ?? context.parsed;

              // porcentaje respecto a la capacidad total del estanque
              const total = capacities[context.dataIndex] || 0;
              const percent =
                total > 0 ? ((value / total) * 100).toFixed(1) : "0.0";

              return `${label}: ${value.toLocaleString()} L (${percent}%)`;
            },
          },
        },
        legend: {
          labels: {
            color: "#0f172a",
            usePointStyle: true,
          },
        },
      },
      scales: {
        x: {
          stacked: true, // 👈 barras apiladas
          ticks: {
            color: "#1f2937",
            autoSkip: false,
            maxRotation: 0,
            minRotation: 0,
          },
          grid: {
            display: false,
          },
        },
        y: {
          stacked: true, // 👈 barras apiladas
          ticks: {
            color: "#1f2937",
          },
          grid: {
            color: "#e5e7eb",
          },
          beginAtZero: true,
          suggestedMax: maxCapacity, // 👈 escala según capacidad
        },
      },
    },
  };
}

function renderFuelCharts() {
  const dataElement = document.getElementById("fuel-dashboard-data");
  if (!dataElement) return;

  let branches;
  try {
    branches = JSON.parse(dataElement.textContent);
  } catch (error) {
    console.error(
      "No se pudo interpretar los datos del dashboard de combustible",
      error,
    );
    return;
  }

  console.log("branches JSON:", branches);

  branches.forEach((branch, index) => {
    const canvas = document.getElementById(`fuel-chart-${index}`);
    if (!canvas) return;

    const config = buildChartConfig(branch, index);
    // eslint-disable-next-line no-undef, no-new
    new Chart(canvas, config);
  });
}

document.addEventListener("DOMContentLoaded", renderFuelCharts);
