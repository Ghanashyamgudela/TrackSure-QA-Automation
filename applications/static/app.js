const byId = (id) => document.getElementById(id);
let staffSession = null;
let csrfToken = "";

function showMessage(element, message, state = "error") {
    if (!element) return;
    element.textContent = message;
    element.hidden = false;
    element.className = `inline-message ${state}`;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json();
    if (!response.ok) {
        const detail = Array.isArray(data.detail)
            ? data.detail.map((item) => item.msg).join(", ")
            : data.detail;
        throw new Error(detail || "The request could not be completed.");
    }
    return data;
}

function statusLabel(status) {
    return String(status || "").replaceAll("_", " ");
}

function addShipmentRow(shipment) {
    const row = document.createElement("tr");
    const values = [
        shipment.tracking_id,
        shipment.sender_name,
        shipment.receiver_name,
        shipment.receiver_address,
    ];
    for (const [index, value] of values.entries()) {
        const cell = document.createElement("td");
        cell.textContent = value || "—";
        if (index === 0) cell.className = "tracking-cell";
        row.append(cell);
    }

    const statusCell = document.createElement("td");
    const badge = document.createElement("span");
    badge.className = `status-badge status-${String(shipment.status).toLowerCase()}`;
    badge.textContent = statusLabel(shipment.status);
    statusCell.append(badge);
    row.append(statusCell);

    const dateCell = document.createElement("td");
    dateCell.textContent = shipment.created_at
        ? new Date(shipment.created_at).toLocaleString()
        : "—";
    row.append(dateCell);

    const actions = document.createElement("td");
    const trackLink = document.createElement("a");
    trackLink.className = "row-action";
    trackLink.href = `/track?tracking_id=${encodeURIComponent(shipment.tracking_id)}`;
    trackLink.textContent = "Track";
    actions.append(trackLink);

    if (
        staffSession &&
        ["admin", "operator"].includes(staffSession.role) &&
        !["DELIVERED", "CANCELLED"].includes(shipment.status)
    ) {
        const advance = document.createElement("button");
        advance.type = "button";
        advance.className = "button button-small row-advance";
        advance.textContent = "Advance";
        advance.addEventListener("click", () => advanceShipment(shipment));
        actions.append(" ", advance);
    }
    row.append(actions);
    byId("shipment-rows").append(row);
}

function currentFilters() {
    const search = byId("search-input");
    if (!search) return {};
    return {
        q: search.value.trim(),
        status: byId("status-filter").value,
        sort_by: byId("sort-by").value,
        order: byId("sort-order").value
    };
}

async function loadShipments() {
    const rows = byId("shipment-rows");
    if (!rows) return;
    const tableMessage = byId("table-message");
    tableMessage.hidden = true;
    rows.replaceChildren();
    try {
        const params = new URLSearchParams(currentFilters());
        const shipments = await fetchJson(`/api/shipments?${params}`);
        for (const shipment of shipments) addShipmentRow(shipment);
        byId("empty-table").hidden = shipments.length > 0;
        if (shipments.length === 0) {
            byId("empty-table").querySelector("strong").textContent =
                currentFilters().q || currentFilters().status
                    ? "No shipments found"
                    : "No shipments yet";
        }
    } catch (error) {
        byId("empty-table").hidden = true;
        showMessage(
            tableMessage,
            error instanceof Error ? error.message : "Could not load shipments."
        );
    }
}

function renderWeeklyChart(weeklyShipments) {
    const chart = byId("weekly-chart");
    if (!chart) return;
    chart.replaceChildren();
    const maxCount = Math.max(1, ...weeklyShipments.map((day) => day.count));
    for (const day of weeklyShipments) {
        const column = document.createElement("div");
        column.className = "week-day";
        column.setAttribute("aria-label", `${day.date}: ${day.count} shipments`);
        const count = document.createElement("strong");
        count.textContent = day.count;
        const track = document.createElement("div");
        track.className = "bar-track";
        const fill = document.createElement("span");
        fill.style.height = `${Math.max(day.count ? 6 : 0, day.count / maxCount * 100)}%`;
        track.append(fill);
        const label = document.createElement("small");
        label.textContent = new Date(`${day.date}T00:00:00`).toLocaleDateString(
            undefined,
            {weekday: "short"}
        );
        column.append(count, track, label);
        chart.append(column);
    }
}

function renderStatusChart(statusDistribution, total) {
    const chart = byId("status-chart");
    if (!chart) return;
    chart.replaceChildren();
    const entries = Object.entries(statusDistribution);
    if (!entries.length) {
        const empty = document.createElement("p");
        empty.className = "empty-chart";
        empty.textContent = "No shipment data to display yet.";
        chart.append(empty);
        return;
    }
    const order = ["BOOKED", "PICKED_UP", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"];
    entries.sort(([left], [right]) => order.indexOf(left) - order.indexOf(right));
    for (const [status, count] of entries) {
        const row = document.createElement("div");
        row.className = "distribution-row";
        const name = document.createElement("span");
        name.textContent = statusLabel(status);
        const track = document.createElement("div");
        track.className = "distribution-track";
        const fill = document.createElement("span");
        fill.style.width = `${total ? count / total * 100 : 0}%`;
        fill.classList.add(`distribution-${status.toLowerCase()}`);
        track.append(fill);
        const value = document.createElement("strong");
        value.textContent = count;
        row.append(name, track, value);
        chart.append(row);
    }
}

function renderRecentActivity(activity) {
    const container = byId("recent-activity");
    if (!container) return;
    container.replaceChildren();
    if (!activity.length) {
        const empty = document.createElement("p");
        empty.className = "empty-chart";
        empty.textContent = "Shipment activity will appear here as parcels move.";
        container.append(empty);
        return;
    }
    for (const event of activity) {
        const row = document.createElement("article");
        row.className = "activity-item";
        const icon = document.createElement("span");
        icon.className = `activity-marker status-${String(event.status).toLowerCase()}`;
        icon.setAttribute("aria-hidden", "true");
        const detail = document.createElement("div");
        detail.className = "activity-detail";
        const title = document.createElement("strong");
        title.textContent = event.tracking_id;
        const subtitle = document.createElement("span");
        subtitle.textContent = `${statusLabel(event.status)} · ${event.receiver_name}`;
        detail.append(title, subtitle);
        const time = document.createElement("time");
        time.dateTime = event.updated_at;
        time.textContent = new Date(event.updated_at).toLocaleString();
        row.append(icon, detail, time);
        container.append(row);
    }
}

async function loadAnalytics() {
    const analyticsCard = byId("total-count");
    const reportStats = byId("report-total");
    if (!analyticsCard && !reportStats && !byId("weekly-chart")) return;
    try {
        const data = await fetchJson("/api/analytics");
        if (analyticsCard) {
            byId("total-count").textContent = data.total;
            byId("booked-count").textContent = data.booked;
            byId("transit-count").textContent = data.in_transit;
            byId("delivered-count").textContent = data.delivered;
            byId("delayed-count").textContent = data.delayed;
            byId("success-count").textContent = `${data.delivery_success_percentage}%`;
        }
        if (reportStats) {
            byId("report-total").textContent = data.total;
            byId("report-booked").textContent = data.booked;
            byId("report-transit").textContent = data.in_transit;
            byId("report-delivered").textContent = data.delivered;
            byId("report-delayed").textContent = data.delayed;
            byId("report-success").textContent = `${data.delivery_success_percentage}%`;
        }
        renderWeeklyChart(data.weekly_shipments);
        renderStatusChart(data.status_distribution, data.total);
        renderRecentActivity(data.recent_activity || []);
    } catch (error) {
        const message = error instanceof Error ? error.message : "Could not load analytics.";
        const activity = byId("recent-activity");
        if (activity) showMessage(activity, message);
        const weekly = byId("weekly-chart");
        if (weekly) showMessage(weekly, message);
    }
}

async function loadAlerts() {
    const container = byId("delayed-alerts");
    if (!container) return;
    try {
        const alerts = await fetchJson("/api/alerts/delayed");
        container.replaceChildren();
        const badge = byId("delayed-badge");
        if (badge) badge.textContent = alerts.length;
        if (alerts.length === 0) {
            const empty = document.createElement("p");
            empty.className = "empty-chart";
            empty.textContent = "No delayed shipments. Your network is on track.";
            container.append(empty);
            return;
        }
        for (const alert of alerts) {
            const item = document.createElement("article");
            item.className = "alert-item";
            const information = document.createElement("div");
            const id = document.createElement("strong");
            id.textContent = alert.tracking_id;
            const status = document.createElement("span");
            status.className = `status-badge status-${String(alert.status).toLowerCase()}`;
            status.textContent = statusLabel(alert.status);
            const reason = document.createElement("p");
            reason.textContent = alert.reason || `${alert.delayed_hours} hours without a status update`;
            information.append(id, status, reason);
            item.append(information);
            if (staffSession && ["admin", "operator"].includes(staffSession.role)) {
                const button = document.createElement("button");
                button.type = "button";
                button.className = "button button-small button-soft";
                button.textContent = alert.reason ? "Update reason" : "Add reason";
                button.addEventListener("click", () => updateDelayReason(alert.tracking_id));
                item.append(button);
            }
            container.append(item);
        }
    } catch (error) {
        showMessage(
            container,
            error instanceof Error ? error.message : "Could not load delayed shipments."
        );
    }
}

async function refreshCsrf() {
    try {
        const data = await fetchJson("/api/auth/csrf");
        csrfToken = data.csrf_token;
        return true;
    } catch {
        return false;
    }
}

async function loadStaffUsers() {
    const list = byId("staff-list");
    if (!list) return;
    try {
        const users = await fetchJson("/api/admin/users");
        list.replaceChildren();
        for (const user of users) {
            const row = document.createElement("div");
            row.className = "staff-row";
            const name = document.createElement("span");
            name.textContent = `${user.username} · ${user.role} · ${user.is_active ? "Active" : "Inactive"}`;
            const action = document.createElement("button");
            action.type = "button";
            action.className = "button button-small button-soft";
            action.textContent = user.is_active ? "Deactivate" : "Reactivate";
            action.disabled = user.username === staffSession.username && user.is_active;
            action.addEventListener("click", () => setStaffUserActive(user));
            row.append(name, action);
            list.append(row);
        }
    } catch (error) {
        showMessage(
            byId("staff-result"),
            error instanceof Error ? error.message : "Could not load staff accounts."
        );
    }
}

async function setStaffUserActive(user) {
    if (!csrfToken && !await refreshCsrf()) return;
    try {
        const result = await fetchJson(
            `/api/admin/users/${user.id}/active?active=${!user.is_active}`,
            {method: "PATCH", headers: {"X-CSRF-Token": csrfToken}}
        );
        showMessage(byId("staff-result"), `${result.username} account updated.`, "success");
        await loadStaffUsers();
    } catch (error) {
        showMessage(
            byId("staff-result"),
            error instanceof Error ? error.message : "Could not update account."
        );
    }
}

async function advanceShipment(shipment) {
    const transitions = {
        BOOKED: "PICKED_UP",
        PICKED_UP: "IN_TRANSIT",
        IN_TRANSIT: "OUT_FOR_DELIVERY",
        OUT_FOR_DELIVERY: "DELIVERED"
    };
    const next = transitions[shipment.status];
    if (!next || !await refreshCsrf()) return;
    const payload = {status: next};
    if (next === "DELIVERED") {
        const receiverName = window.prompt("Receiver name confirming delivery:");
        if (!receiverName) return;
        const remarks = window.prompt("Delivery remarks:");
        if (!remarks) return;
        const signature = window.prompt("Optional typed receiver signature/confirmation:");
        payload.delivery_proof = {receiver_name: receiverName, remarks};
        if (signature) payload.delivery_proof.signature = signature;
    }
    try {
        await fetchJson(`/api/shipments/${shipment.id}/status`, {
            method: "PUT",
            headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken},
            body: JSON.stringify(payload)
        });
        await Promise.all([loadShipments(), loadAnalytics(), loadAlerts()]);
    } catch (error) {
        window.alert(error instanceof Error ? error.message : "Could not update shipment.");
    }
}

async function updateDelayReason(trackingId) {
    const reason = window.prompt(`Delay reason for ${trackingId}:`);
    if (!reason || !await refreshCsrf()) return;
    try {
        const shipments = await fetchJson(
            `/api/shipments?${new URLSearchParams({q: trackingId})}`
        );
        const shipment = shipments.find((item) => item.tracking_id === trackingId);
        if (!shipment) return;
        await fetchJson(`/api/shipments/${shipment.id}/delay-reason`, {
            method: "PUT",
            headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken},
            body: JSON.stringify({reason})
        });
        await loadAlerts();
    } catch (error) {
        window.alert(error instanceof Error ? error.message : "Could not save delay reason.");
    }
}

async function initializeStaff() {
    const response = await fetch("/api/auth/me");
    if (!response.ok) return;
    const session = await response.json();
    const sessionPanel = byId("settings-session");
    if (sessionPanel) {
        sessionPanel.hidden = !session.authenticated;
        const guestMessage = byId("settings-guest");
        if (guestMessage) guestMessage.hidden = session.authenticated;
    }
    if (!session.authenticated) return;

    staffSession = session;
    if (byId("settings-username")) byId("settings-username").textContent = session.username;
    if (byId("settings-role")) byId("settings-role").textContent = session.role;
    if (byId("settings-admin-notice")) {
        byId("settings-admin-notice").hidden = session.role === "admin";
    }
    if (byId("login-link")) byId("login-link").hidden = true;
    if (byId("staff-session")) byId("staff-session").hidden = false;
    if (byId("staff-name")) byId("staff-name").textContent = session.username;
    if (byId("staff-role")) byId("staff-role").textContent = session.role;
    if (byId("staff-avatar")) {
        byId("staff-avatar").textContent = session.username.slice(0, 2).toUpperCase();
    }
    const adminPanel = byId("admin-panel");
    if (adminPanel && session.role === "admin") adminPanel.hidden = false;
    await refreshCsrf();
    if (session.role === "admin") await loadStaffUsers();
}

function updateExportLink() {
    const exportLink = byId("export-link");
    if (exportLink) {
        exportLink.href = `/api/shipments/export.csv?${new URLSearchParams(currentFilters())}`;
    }
}

function initializeFilters() {
    if (!byId("search-input")) return;
    for (const id of ["search-input", "status-filter", "sort-by", "sort-order"]) {
        const control = byId(id);
        control.addEventListener(
            id === "search-input" ? "input" : "change",
            () => {
                loadShipments();
                updateExportLink();
            }
        );
    }
}

function initializeStaffForm() {
    const form = byId("staff-form");
    if (!form) return;
    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        if (!csrfToken && !await refreshCsrf()) return;
        const fields = Object.fromEntries(new FormData(form));
        try {
            const result = await fetchJson("/api/admin/users", {
                method: "POST",
                headers: {"Content-Type": "application/json", "X-CSRF-Token": csrfToken},
                body: JSON.stringify(fields)
            });
            showMessage(byId("staff-result"), `Created ${result.role}: ${result.username}`, "success");
            form.reset();
            await loadStaffUsers();
        } catch (error) {
            showMessage(
                byId("staff-result"),
                error instanceof Error ? error.message : "Could not create account."
            );
        }
    });
}

function initializeSidebar() {
    const sidebar = byId("sidebar");
    const toggle = byId("mobile-menu");
    const scrim = byId("sidebar-scrim");
    if (!sidebar || !toggle || !scrim) return;
    const close = () => {
        sidebar.classList.remove("is-open");
        scrim.classList.remove("is-visible");
        toggle.setAttribute("aria-expanded", "false");
        document.body.classList.remove("sidebar-open");
    };
    toggle.addEventListener("click", () => {
        const open = !sidebar.classList.contains("is-open");
        sidebar.classList.toggle("is-open", open);
        scrim.classList.toggle("is-visible", open);
        toggle.setAttribute("aria-expanded", String(open));
        document.body.classList.toggle("sidebar-open", open);
    });
    scrim.addEventListener("click", close);
    sidebar.querySelectorAll("a").forEach((link) => link.addEventListener("click", close));
    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") close();
    });
}

function initializeLogout() {
    const button = byId("logout-button");
    if (!button) return;
    button.addEventListener("click", async () => {
        if (!csrfToken && !await refreshCsrf()) return;
        try {
            await fetchJson("/api/auth/logout", {
                method: "POST",
                headers: {"X-CSRF-Token": csrfToken}
            });
            window.location.assign("/login");
        } catch (error) {
            window.alert(error instanceof Error ? error.message : "Could not sign out.");
        }
    });
}

function initializeCurrentDate() {
    const date = byId("current-date");
    if (date) {
        date.textContent = new Intl.DateTimeFormat(undefined, {
            weekday: "short", month: "short", day: "numeric"
        }).format(new Date());
    }
}

function initializeReportsExport() {
    const link = byId("reports-export");
    if (link) link.href = "/api/shipments/export.csv";
}

async function initializeApp() {
    initializeSidebar();
    initializeCurrentDate();
    initializeFilters();
    initializeStaffForm();
    initializeLogout();
    initializeReportsExport();
    await initializeStaff();
    await Promise.all([loadAnalytics(), loadShipments(), loadAlerts()]);
    if (byId("dashboard-root")) {
        window.setInterval(
            () => Promise.all([loadAnalytics(), loadShipments(), loadAlerts()]),
            30000
        );
    }
}

initializeApp();
