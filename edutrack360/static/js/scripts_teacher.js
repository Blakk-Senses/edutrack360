document.addEventListener("DOMContentLoaded", function () {
    // Sample Data for Performance Trends
    const ctx = document.getElementById("performanceChart").getContext("2d");
    new Chart(ctx, {
        type: "line",
        data: {
            labels: ["Term 1", "Term 2", "Term 3"],
            datasets: [{
                label: "Average Score",
                data: [75, 82, 78],
                borderColor: "gold",
                borderWidth: 2,
                fill: false
            }]
        },
        options: {
            responsive: true,
            scales: {
                y: { beginAtZero: true }
            }
        }
    });

    // Sample Data for Student Results
    const studentResults = [
        { name: "Alice Johnson", subject: "Math", score: 85, grade: "A" },
        { name: "Bob Smith", subject: "Science", score: 78, grade: "B" },
        { name: "Charlie Brown", subject: "English", score: 92, grade: "A" }
    ];

    // Populate Table with Student Results
    const resultsTable = document.getElementById("resultsTable");
    studentResults.forEach(student => {
        const row = `<tr>
            <td>${student.name}</td>
            <td>${student.subject}</td>
            <td>${student.score}</td>
            <td>${student.grade}</td>
        </tr>`;
        resultsTable.innerHTML += row;
    });
});
