// Initialize charts for dashboard
document.addEventListener('DOMContentLoaded', function() {
    const chartElements = document.querySelectorAll('[data-chart]');
    
    chartElements.forEach(element => {
        const chartType = element.dataset.chart;
        const chartData = JSON.parse(element.dataset.chartData);
        
        switch(chartType) {
            case 'expense':
                createExpenseChart(element, chartData);
                break;
            case 'category':
                createCategoryChart(element, chartData);
                break;
        }
    });
});

function createExpenseChart(element, data) {
    new Chart(element, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: 'Expenses',
                data: data.values,
                borderColor: 'rgb(255, 99, 132)',
                tension: 0.1
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: 'Monthly Expenses'
                }
            }
        }
    });
}

function createCategoryChart(element, data) {
    new Chart(element, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: [
                    '#ff6384',
                    '#36a2eb',
                    '#cc65fe',
                    '#ffce56',
                    '#4bc0c0'
                ]
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'right',
                },
                title: {
                    display: true,
                    text: 'Expense Categories'
                }
            }
        }
    });
}
