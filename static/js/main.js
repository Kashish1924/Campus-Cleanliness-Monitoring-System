document.addEventListener("DOMContentLoaded", () => {
    const pageLoader = document.getElementById("pageLoader");
    const complaintIdInput = document.getElementById("complaint_id");
    const trackComplaintForm = document.getElementById("trackComplaintForm");
    const complaintDetailsContainer = document.getElementById("complaintDetailsContainer");
    const inlineMessage = document.getElementById("trackComplaintInlineMessage");
    const deleteForms = document.querySelectorAll(".delete-complaint-form");
    const deleteScheduleForms = document.querySelectorAll(".delete-schedule-form");
    const dashboardChartData = window.dashboardChartData;
    const toastElements = document.querySelectorAll(".toast");

    if (pageLoader) {
        window.setTimeout(() => {
            pageLoader.classList.add("hidden");
        }, 250);
    }

    if (toastElements.length && window.bootstrap) {
        toastElements.forEach((toastElement) => {
            const toast = new window.bootstrap.Toast(toastElement);
            toast.show();
        });
    }

    if (complaintIdInput) {
        complaintIdInput.addEventListener("input", () => {
            complaintIdInput.value = complaintIdInput.value.toUpperCase();
        });
    }

    if (trackComplaintForm && complaintDetailsContainer && inlineMessage && complaintIdInput) {
        trackComplaintForm.addEventListener("submit", async (event) => {
            event.preventDefault();

            const complaintId = complaintIdInput.value.trim().toUpperCase();
            if (!complaintId) {
                inlineMessage.innerHTML = '<div class="alert alert-danger mb-0">Please enter a complaint ID to continue.</div>';
                complaintDetailsContainer.innerHTML = "";
                return;
            }

            const lookupUrl = trackComplaintForm.dataset.lookupUrl.replace("COMPLAINT_ID_PLACEHOLDER", encodeURIComponent(complaintId));

            try {
                const response = await fetch(lookupUrl, {
                    headers: {
                        "X-Requested-With": "XMLHttpRequest"
                    }
                });
                const data = await response.json();

                if (!response.ok) {
                    inlineMessage.innerHTML = `<div class="alert alert-warning mb-0">${data.message}</div>`;
                    complaintDetailsContainer.innerHTML = "";
                    window.history.replaceState({}, "", `/track?complaint_id=${encodeURIComponent(complaintId)}`);
                    return;
                }

                inlineMessage.innerHTML = "";
                complaintDetailsContainer.innerHTML = buildComplaintDetailsCard(data.complaint);
                window.history.replaceState({}, "", `/track?complaint_id=${encodeURIComponent(complaintId)}`);
            } catch (_error) {
                inlineMessage.innerHTML = '<div class="alert alert-danger mb-0">Unable to fetch complaint details right now. Please try again.</div>';
            }
        });
    }

    if (deleteForms.length) {
        deleteForms.forEach((form) => {
            form.addEventListener("submit", (event) => {
                const confirmed = window.confirm("Are you sure you want to delete this complaint? This action cannot be undone.");
                if (!confirmed) {
                    event.preventDefault();
                }
            });
        });
    }

    if (deleteScheduleForms.length) {
        deleteScheduleForms.forEach((form) => {
            form.addEventListener("submit", (event) => {
                const confirmed = window.confirm("Are you sure you want to delete this cleaning schedule?");
                if (!confirmed) {
                    event.preventDefault();
                }
            });
        });
    }

    if (dashboardChartData && window.Chart) {
        const statusChartElement = document.getElementById("statusChart");
        const priorityChartElement = document.getElementById("priorityChart");

        if (statusChartElement) {
            new window.Chart(statusChartElement, {
                type: "pie",
                data: {
                    labels: dashboardChartData.status_labels,
                    datasets: [{
                        data: dashboardChartData.status_values,
                        backgroundColor: ["#f0b429", "#4f86c6", "#0ea5e9", "#20c997", "#6c757d"],
                        borderWidth: 0
                    }]
                },
                options: {
                    plugins: {
                        legend: {
                            position: "bottom"
                        }
                    }
                }
            });
        }

        if (priorityChartElement) {
            new window.Chart(priorityChartElement, {
                type: "bar",
                data: {
                    labels: dashboardChartData.priority_labels,
                    datasets: [{
                        label: "Complaints",
                        data: dashboardChartData.priority_values,
                        backgroundColor: ["#7dd3fc", "#0b5d52", "#ef4444"],
                        borderRadius: 8
                    }]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: {
                            beginAtZero: true,
                            ticks: {
                                precision: 0
                            }
                        }
                    },
                    plugins: {
                        legend: {
                            display: false
                        }
                    }
                }
            });
        }
    }
});

function buildComplaintDetailsCard(complaint) {
    const statusClass = `status-${complaint.status.toLowerCase().replace(/\s+/g, "-")}`;
    const assignedStaff = complaint.assigned_staff || "Not assigned yet";
    const remarks = complaint.remarks || "No remarks available";
    const imageMarkup = complaint.image_url
        ? `
            <div class="col-12">
                <strong>Uploaded Image:</strong>
                <div class="mt-3">
                    <img src="${complaint.image_url}" alt="Complaint Image" class="img-fluid complaint-image rounded-3 border">
                </div>
            </div>
        `
        : "";

    return `
        <div class="card shadow-sm border-0">
            <div class="card-body p-4">
                <div class="d-flex flex-wrap justify-content-between align-items-start gap-3 mb-3">
                    <div>
                        <h2 class="h4 mb-1">Complaint Details</h2>
                        <p class="text-muted mb-0">Complaint ID: <strong>${complaint.complaint_id}</strong></p>
                    </div>
                    <span class="badge status-badge ${statusClass}">${complaint.status}</span>
                </div>

                <div class="row g-3">
                    <div class="col-md-6"><strong>Department:</strong> ${complaint.department}</div>
                    <div class="col-md-6"><strong>Role:</strong> ${complaint.role}</div>
                    <div class="col-md-6"><strong>Building:</strong> ${complaint.building}</div>
                    <div class="col-md-6"><strong>Floor:</strong> ${complaint.floor}</div>
                    <div class="col-md-6"><strong>Location:</strong> ${complaint.location}</div>
                    <div class="col-md-6"><strong>Area Type:</strong> ${complaint.area_type}</div>
                    <div class="col-md-6"><strong>Issue Category:</strong> ${complaint.issue_category}</div>
                    <div class="col-md-6"><strong>Priority:</strong> ${complaint.priority}</div>
                    <div class="col-12"><strong>Description:</strong> ${complaint.description}</div>
                    <div class="col-md-6"><strong>Assigned Staff:</strong> ${assignedStaff}</div>
                    <div class="col-md-6"><strong>Remarks:</strong> ${remarks}</div>
                    <div class="col-md-6"><strong>Created At:</strong> ${complaint.created_at}</div>
                    <div class="col-md-6"><strong>Updated At:</strong> ${complaint.updated_at}</div>
                    ${imageMarkup}
                </div>
            </div>
        </div>
    `;
}
