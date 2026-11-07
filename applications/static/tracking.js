const trackingForm = document.getElementById("tracking-form");
const trackingInput = document.getElementById("tracking_id");
const trackingResult = document.getElementById("tracking-result");
const trackingError = document.getElementById("tracking-error");
const trackingLoading = document.getElementById("tracking-loading");
const trackButton = document.getElementById("track-btn");

function formatTrackingDate(value) {
    return value ? new Date(value).toLocaleString() : "Awaiting this step";
}

function appendHistoryItem(container, event) {
    const item = document.createElement("li");
    const marker = document.createElement("span");
    marker.className = "history-marker";
    marker.setAttribute("aria-hidden", "true");
    const content = document.createElement("div");
    content.className = "history-content";
    const title = document.createElement("strong");
    title.textContent = String(event.status).replaceAll("_", " ");
    const time = document.createElement("time");
    time.dateTime = event.updated_at;
    time.textContent = formatTrackingDate(event.updated_at);
    content.append(title, time);
    item.append(marker, content);
    container.append(item);
}

function renderTimeline(data) {
    const timeline = document.getElementById("timeline");
    timeline.replaceChildren();
    for (const step of data.timeline) {
        const item = document.createElement("li");
        item.className = step.current ? "current" : (step.completed ? "completed" : "");
        if (step.status === "CANCELLED") item.classList.add("cancelled");
        const marker = document.createElement("span");
        marker.className = "timeline-marker";
        marker.setAttribute("aria-hidden", "true");
        const detail = document.createElement("div");
        detail.className = "timeline-step-detail";
        const title = document.createElement("strong");
        title.textContent = String(step.status).replaceAll("_", " ");
        const time = document.createElement("time");
        if (step.updated_at) time.dateTime = step.updated_at;
        time.textContent = formatTrackingDate(step.updated_at);
        detail.append(title, time);
        item.append(marker, detail);
        timeline.append(item);
    }
}

function renderTrackingHistory(history) {
    const list = document.getElementById("tracking-history");
    list.replaceChildren();
    if (history.length === 0) {
        const empty = document.createElement("li");
        empty.className = "empty-history";
        empty.textContent = "No shipment updates have been recorded yet.";
        list.append(empty);
        return;
    }
    for (const item of [...history].reverse()) appendHistoryItem(list, item);
}

function renderDeliveryProof(proof) {
    const panel = document.getElementById("delivery-proof");
    panel.hidden = !proof;
    if (!proof) return;
    document.getElementById("proof-name").textContent = proof.receiver_name;
    const time = document.getElementById("proof-time");
    time.textContent = formatTrackingDate(proof.confirmed_at);
    time.dateTime = proof.confirmed_at;
    document.getElementById("proof-remarks").textContent = proof.remarks;
}

function renderShipment(data) {
    document.getElementById("result-id").textContent = data.tracking_id;
    const status = document.getElementById("result-status");
    status.textContent = String(data.status).replaceAll("_", " ");
    status.className = `status-badge status-${String(data.status).toLowerCase()}`;
    document.getElementById("result-sender").textContent = data.sender_name || "—";
    document.getElementById("result-receiver").textContent = data.receiver_name || "—";
    document.getElementById("result-destination").textContent = data.receiver_address || "—";
    document.getElementById("result-parcel").textContent = data.parcel_description || "—";
    const eta = document.getElementById("result-eta");
    const etaContainer = document.getElementById("eta-detail");
    etaContainer.hidden = !data.estimated_delivery;
    if (data.estimated_delivery) {
        eta.textContent = new Date(data.estimated_delivery).toLocaleDateString();
    }
    renderTimeline(data);
    renderTrackingHistory(data.history || []);
    renderDeliveryProof(data.delivery_proof);
    trackingResult.hidden = false;
}

trackingForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const trackingId = trackingInput.value.trim();
    trackingResult.hidden = true;
    trackingError.hidden = true;
    trackingError.textContent = "";

    if (!trackingId) {
        trackingError.textContent = "Enter a tracking ID to search for a shipment.";
        trackingError.hidden = false;
        trackingInput.focus();
        return;
    }

    trackButton.disabled = true;
    trackingLoading.hidden = false;
    try {
        const response = await fetch(`/api/track/${encodeURIComponent(trackingId)}`);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.detail || "We couldn't find that shipment.");
        }
        renderShipment(data);
    } catch (error) {
        trackingError.textContent = error instanceof Error
            ? error.message
            : "Unable to connect to the server.";
        trackingError.hidden = false;
    } finally {
        trackingLoading.hidden = true;
        trackButton.disabled = false;
    }
});

if (trackingInput.value.trim()) trackingForm.requestSubmit();
