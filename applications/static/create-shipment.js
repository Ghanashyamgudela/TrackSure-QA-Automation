const form = document.getElementById("shipment-form");
const resultMessage = document.getElementById("result");
const submitButton = document.getElementById("create-btn");

form.addEventListener("submit", async (event) => {
    event.preventDefault();
    resultMessage.textContent = "";
    resultMessage.className = "notification";

    const shipmentData = {
        sender_name: document.getElementById("sender_name").value.trim(),
        receiver_name: document.getElementById("receiver_name").value.trim(),
        receiver_address: document.getElementById("receiver_address").value.trim(),
        parcel_description: document.getElementById("parcel_description").value.trim()
    };

    if (Object.values(shipmentData).some((value) => !value)) {
        resultMessage.textContent = "Please complete all shipment details.";
        resultMessage.classList.add("notification-error");
        return;
    }

    submitButton.disabled = true;
    submitButton.classList.add("is-loading");
    submitButton.querySelector("span").textContent = "Creating shipment…";

    try {
        const response = await fetch("/api/shipments", {
            method: "POST",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(shipmentData)
        });
        const data = await response.json();

        if (!response.ok) {
            const detail = Array.isArray(data.detail)
                ? data.detail.map((item) => item.msg).join(", ")
                : data.detail;
            throw new Error(detail || "Unable to create shipment. Please try again.");
        }

        resultMessage.textContent = `Shipment Created! Tracking ID: ${data.tracking_id}`;
        resultMessage.classList.add("notification-success");
        form.reset();
    } catch (error) {
        resultMessage.textContent = error instanceof Error
            ? error.message
            : "Unable to connect to the server.";
        resultMessage.classList.add("notification-error");
    } finally {
        submitButton.disabled = false;
        submitButton.classList.remove("is-loading");
        submitButton.querySelector("span").textContent = "Create shipment";
    }
});
