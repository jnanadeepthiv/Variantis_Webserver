document.addEventListener("DOMContentLoaded", function () {
  //DEBUG //console.log("colour_alignment.js loaded");
  attachEventListeners(); // Attach event listeners initially
});

// Function to attach event listeners dynamically after content loads
function attachEventListeners() {
  // Get CSRF token from the hidden field in the form
  const csrf_token = document.querySelector('input[name="csrf_token"]').value;

  //DEBUG //console.log("Attaching event listeners");
  const submitButton = document.querySelector('.submit-button');
  if (submitButton) {
    submitButton.addEventListener("click", updateQueryrequest); // Removed () to pass function reference
  }
}

function updateQueryrequest(event) {
  //DEBUG //console.log("updateQueryrequest called");
  event.preventDefault();

  // Retrieve session ID from the hidden input field
  const sessionIdElement = document.getElementById('session-id');
  if (!sessionIdElement) {
    console.error("Session ID element not found!");
    return;
  }
  const sessionId = sessionIdElement.value;

  // Retrieve the CSRF token inside the function
  const csrf_token = document.querySelector('input[name="csrf_token"]').value;
  if (!csrf_token) {
    console.error("CSRF token not found!");
    return;
    }

  const customqueryrequest = document.getElementById('query').value;
  const customsubjectrequest = document.getElementById('subject').value;

  if (customqueryrequest === customsubjectrequest) {
    alert("Both QueryId and SubjectId are the same; Select different IDs");
    return;
  }

  const customalignmentrequest = {
    queryrequest: customqueryrequest,
    subjectrequest: customsubjectrequest,
    session_id: sessionId
  };

  //DEBUG //console.log("Sending request:", customalignmentrequest);

  fetch('/sharmaglab/variantis/alignment', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRF-TOKEN': csrf_token 
    },
    body: JSON.stringify(customalignmentrequest),
    credentials: 'include'  // Ensures cookies are sent with the request
  })
    .then(response => response.json())
    .then(data => {
      const resultDiv = document.getElementById("storedquerysubject");
      resultDiv.style.display = "block"; // Show the result section

      if (data.colour_coded_alignment && data.stats) {
        
        document.getElementById("colour_coded_alignment").innerHTML = data.colour_coded_alignment;

        // Populate the stats table
        const statsTable = document.getElementById("stats_table");
        statsTable.innerHTML = `
          <thead>
            <tr>
              <th style="border: 1px solid black; padding: 8px;">Category</th>
              <th style="border: 1px solid black; padding: 8px;">Count</th>
              <th style="border: 1px solid black; padding: 8px;">Percentage</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td style="border: 1px solid black; padding: 8px;">Identical</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.identical}</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.identical_percent.toFixed(2)}%</td>
            </tr>
            <tr>
              <td style="border: 1px solid black; padding: 8px;">Transitions</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.transitions}</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.transitions_percent.toFixed(2)}%</td>
            </tr>
            <tr>
              <td style="border: 1px solid black; padding: 8px;">Transversions</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.transversions}</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.transversions_percent.toFixed(2)}%</td>
            </tr>
            <tr>
              <td style="border: 1px solid black; padding: 8px;">Gapes</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.gaps}</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.gaps_percent.toFixed(2)}%</td>
            </tr>
            <tr>
              <td style="border: 1px solid black; padding: 8px;">Ambiguous (N)</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.unknown}</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.unknown_percent.toFixed(2)}%</td>
            </tr>
            <tr>
              <td style="border: 1px solid black; padding: 8px;">Total Length</td>
              <td style="border: 1px solid black; padding: 8px;">${data.stats.total_length}</td>
              <td style="border: 1px solid black; padding: 8px;">100%</td>
            </tr>
          </tbody>
        `;

        // Render the pie chart
        const ctx = document.getElementById('pie_chart').getContext('2d');
        new Chart(ctx, {
          type: 'pie',
          data: {
            labels: ['Identical', 'Transitions', 'Transversions', 'Gaps','Ambiguous (N)'],
            datasets: [{
              data: [
                data.stats.identical_percent,
                data.stats.transitions_percent,
                data.stats.transversions_percent,
                data.stats.gaps_percent,
                data.stats.unknown_percent
              ],
              backgroundColor: ['#66cc66', 'orange', 'red', 'black', 'grey']
            }]
          },
          options: {
            responsive: false,
            plugins: {
              tooltip: {
                callbacks: {
                  label: function (tooltipItem) {
                    const value = tooltipItem.raw;
                    return `${tooltipItem.label}: ${value.toFixed(2)}%`;
                  }
                }
              }
            }
          }
        });
      } else {
        console.error("Missing data properties: Check server response");
      }
    })
    .catch(error => console.error("Error:", error));
}
