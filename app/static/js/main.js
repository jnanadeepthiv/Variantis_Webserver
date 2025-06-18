// This function shows the default popup with parameters
function showDefaultPopup() {
    alert('Default alignment parameters:\nProgram: EMBOSS Needle\nMatrix: EDNAFULL\nGap Open: 10\nGap Extend: 0.5');
  }
  
  // This function will toggle the visibility of the custom parameters section
  function toggleCustomParams() {
    const params = document.getElementById('custom-params');
    if (params.style.display === 'none' || params.style.display === '') {
        params.style.display = 'block'; // Show the custom parameters
    } else {
        params.style.display = 'none'; // Hide the custom parameters
    }
  }
  
  // Function to start a new session
  async function startSession(csrf_token) {
    try {
        const response = await fetch('/sharmaglab/variantis/start-session', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN': csrf_token,
            },
            credentials: 'include', // Automatically sends cookies!
        });
        const data = await response.json();
        //DEBUG //console.log("startsession awaiting for response");
        //DEBUG //console.log(csrf_token);
        if (data.status === "busy") {
            // Server is busy, notify the user
            //DEBUG //console.log('Server is busy. Please try again later.');
            alert('Server is busy. Please try again later.');
            return false;
        } else {
            // Session is active, proceed
            //DEBUG //console.log('Session started by the fucniton startSession');
            return true;
        }
    } catch (error) {
        console.error('Error starting session:', error);
        alert('Failed to start a session. Please try again.');
        throw error; // Re-throw the error to stop further execution
    }
  }
  
  // This function will update the psa, gap open, and gap extend in case custom parameters are filled
  async function updateCustomparameters(csrf_token) {
    try {
        // Get values of custom parameters from the form
        const customparameters_program = document.getElementById('program').value;
        const customparameters_gapopen = document.getElementById('gapopen').value;
        const customparameters_gapextend = document.getElementById('gapextend').value;
  
        // Validate inputs
        if (isNaN(customparameters_gapopen) || isNaN(customparameters_gapextend)) {
            alert('Gap Open and Gap Extend values must be numeric.');
            return;
        }
  
        if (!customparameters_program || !customparameters_gapopen || !customparameters_gapextend) {
            alert('All fields are required.');
            return;
        }
  
        if (customparameters_gapopen < 1 || customparameters_gapextend < 0) {
            alert('Gap Open must be greater than or equal to 1, and Gap Extend must be greater than or equal to 0.');
            return;
        }
  
        // Prepare form data with file and custom parameters
        const formData = new FormData(document.getElementById('uploadForm'));
        formData.append('psaprogram', customparameters_program);
        formData.append('gapOpen', customparameters_gapopen);
        formData.append('gapExtend', customparameters_gapextend);
  
        // Send data using fetch
        const response = await fetch('/sharmaglab/variantis/uploads', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRF-TOKEN': csrf_token, // Send CSRF token as a custom header
            },
        });
        //DEBUG //console.log("data wait")
        const data = await response.json();
  
        if (data.status === "success") {
            //DEBUG //console.log("Uploaded successfully");
            alert(`File uploaded successfully: ${data.file_name}`);
  
            // Redirect the user to the results page
            if (data.redirect_url) {
                window.location.href = data.redirect_url;
            }
        } else {
            console.error("Upload failed:", data.message);
            alert(`Error: ${data.message}`);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to update custom parameters. Please try again.');
    }
  }
  
  // Function to handle text area input and convert to file
  async function handleTextInput(csrf_token) {
      const textArea = document.getElementById('InputText');
      const fastaText = textArea.value.trim();
      
      if (!fastaText) {
        alert('Please paste FASTA sequences in the text box');
        return false;
      }
      
      // Create a file from the text
      const file = new File([fastaText], "pasted_sequences.fasta", { type: "text/plain" });
      
      // Create form data and append the file
      const formData = new FormData(document.getElementById('uploadForm'));
      formData.delete('fasta_text'); // Remove the text field
      formData.set('file', file); // Add the generated file
      
      // Get custom parameters
      const customparameters_program = document.getElementById('program').value;
      const customparameters_gapopen = document.getElementById('gapopen').value;
      const customparameters_gapextend = document.getElementById('gapextend').value;
      
      // Add parameters to form data
      formData.append('psaprogram', customparameters_program);
      formData.append('gapOpen', customparameters_gapopen);
      formData.append('gapExtend', customparameters_gapextend);
      
      // Send data to server
      try {
        const response = await fetch('/sharmaglab/variantis/uploads', {
          method: 'POST',
          body: formData,
          headers: {
            'X-CSRF-TOKEN': csrf_token,
          },
        });
        
        const data = await response.json();
        
        if (data.status === "success") {
          alert(`Sequences processed successfully`);
          if (data.redirect_url) {
            window.location.href = data.redirect_url;
          }
        } else {
          console.error("Upload failed:", data.message);
          alert(`Error: ${data.message}`);
        }
        return true;
      } catch (error) {
        console.error('Error:', error);
        alert('Failed to process sequences. Please try again.');
        return false;
      }
  }
  
  // Modified function to show sample sequences in text area
  function handleShowSampleClick() {
      fetch(window.sampleFileUrl)
        .then(response => response.text())
        .then(text => {
          document.getElementById('InputText').value = text;
        })
        .catch(error => console.error("Error fetching sample file:", error));
  }
  
  // Initialize the application
  document.addEventListener('DOMContentLoaded', function () {
    //DEBUG //console.log("DOM fully loaded and parsed");
  
    const mainContent = document.getElementById('main-content');
    const spaLinks = document.querySelectorAll('.spa-link');
  
    if (!mainContent) {
        console.error("Error: #main-content element not found");
    } else {
        //DEBUG //console.log("#main-content found");
    }
  
    //DEBUG //console.log("Found", spaLinks.length, "SPA links");
  
    // Handle SPA navigation
    async function loadContent(url) {
        //DEBUG //console.log(`Attempting to load content from: ${url}`);
        try {
            const response = await fetch(url, {
                headers: { 'X-Requested-With': 'XMLHttpRequest' },
            });
  
            if (!response.ok) {
                console.error(`Failed to fetch ${url}: ${response.status} ${response.statusText}`);
                return;
            }
  
            const html = await response.text();
            //DEBUG //console.log(`Successfully fetched content from: ${url}`);
  
            const temp = document.createElement('div');
            temp.innerHTML = html;
            const newContent = temp.querySelector('#main-content')?.innerHTML || html;
  
            if (mainContent.innerHTML !== newContent) {
                //DEBUG //console.log("Updating main content");
                mainContent.innerHTML = newContent;
  
                // Execute any scripts in the new content
                const scripts = temp.querySelectorAll('script');
                scripts.forEach(script => {
                  const newScript = document.createElement('script');
                  newScript.textContent = script.textContent;
                  document.body.appendChild(newScript).remove(); // Execute the script
                });
  
                initDynamicElements();
                //DEBUG //console.log("loadcontent init")
                setupSubmitButton();
                //DEBUG //console.log("loadcontent-submit")
                history.pushState({ path: url }, '', url);
            } else {
                //DEBUG //console.log("No change in content detected");
            }
        } catch (error) {
            console.error('Error loading content:', error);
        }
    }
  
    // Add click handlers to SPA links
    function handleSpaLinkClick(e) {
        e.preventDefault();
        //DEBUG //console.log("SPA link clicked:", this.getAttribute('data-url'));
        //DEBUG //console.log("loadcontent-dataurl")
        loadContent(this.getAttribute('data-url'));
    }
  
    spaLinks.forEach(link => {
        //DEBUG //console.log("Adding event listener to SPA link:", link);
        link.addEventListener('click', handleSpaLinkClick);
    });
  
    // Handle browser back/forward buttons
    window.addEventListener('popstate', function (event) {
        //DEBUG //console.log("Popstate event triggered", event.state);
        if (event.state && event.state.path) {
          //DEBUG //console.log("loadcontent-event")
            loadContent(event.state.path);
        }
    });
  
    // Initialize dynamic components
    function initDynamicElements() {
        //DEBUG //console.log("Initializing dynamic elements");
        document.querySelectorAll('.spa-link').forEach(link => {
            link.removeEventListener('click', handleSpaLinkClick);
            link.addEventListener('click', handleSpaLinkClick);
            //DEBUG //console.log("handlespalink")
        });
        // Reattach event listener for show sample button
        const showSampleBtn = document.getElementById("uploadSampleBtn");
        if (showSampleBtn) {
            showSampleBtn.removeEventListener("click", handleShowSampleClick);
            showSampleBtn.addEventListener("click", handleShowSampleClick);
        }
        setupSubmitButton();
    }
  
    function setupSubmitButton() {
        const submitButton = document.getElementById('startSessionBtn');
        if (submitButton) {
            //DEBUG //console.log("Submit button found. Adding event listener");
            submitButton.removeEventListener('click', handleSubmitButtonClick);
            //DEBUG //console.log("removeevend_hadlesubmit")
            submitButton.addEventListener('click', handleSubmitButtonClick);
            //DEBUG //console.log("addevent_handlesubmit")
        } else {
            console.warn("Submit button not found");
        }
    }
  
    // Helper function for submit button clicks
    async function handleSubmitButtonClick(e) {
      e.preventDefault();
      const submitButton = e.target;
      submitButton.disabled = true;
  
      const csrf_token = document.querySelector('input[name="csrf_token"]')?.value;
      if (!csrf_token) {
          console.error("CSRF token not found");
          submitButton.disabled = false;
          return;
      }
  
      try {
          // Check if both file and text are provided
          const fileInput = document.getElementById('Inputfile');
          const textArea = document.getElementById('InputText');
          
          if (fileInput.files.length > 0 && textArea.value.trim() !== '') {
              alert('Please choose only one input method - either upload a file or paste sequences, not both.');
              return;
          }
  
          const sessionStarted = await startSession(csrf_token);
          
          if (sessionStarted) {
              if (fileInput.files.length > 0) {
                  // File upload case
                  await updateCustomparameters(csrf_token);
              } else if (textArea.value.trim() !== '') {
                  // Text area case
                  await handleTextInput(csrf_token);
              } else {
                  alert('Please either upload a file or paste sequences in the text box');
              }
          }
      } catch (error) {
          console.error('Error:', error);
          alert('An error occurred. Please try again.');
      } finally {
          submitButton.disabled = false;
      }
    }
  
    initDynamicElements();
    //DEBUG //console.log("initdynamic called")
    setupSubmitButton();
    //DEBUG //console.log("setupsubmit called")
  
    
  });