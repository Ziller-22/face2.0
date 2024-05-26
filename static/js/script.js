// Fetch attendance data
function fetchAttendance() {
    fetch(`/attendance_data/{{ class_name }}`)
        .then(response => response.json())
        .then(data => {
            const attendanceList = document.getElementById('attendance-list');
            attendanceList.innerHTML = '';
            data.forEach(item => {
                const listItem = document.createElement('li');
                listItem.textContent = `${item.name} - ${item.time}`;
                attendanceList.appendChild(listItem);
            });
        });
}

// Initial fetch and set interval to update attendance list every 10 seconds
setInterval(fetchAttendance, 10000);
fetchAttendance();

// Show export options dropdown
document.getElementById('export-btn').addEventListener('click', () => {
    document.getElementById('export-options').style.display = 'block';
});

// Function to handle exporting attendance
function exportAttendance(format) {
    fetch(`/export_attendance/{{ class_name }}/${format}`)
        .then(response => response.blob())
        .then(blob => {
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.style.display = 'none';
            a.href = url;
            a.download = `Attendance_{{ class_name }}.${format === 'pdf' ? 'pdf' : 'xlsx'}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
        });
}

// Show email prompt
function showEmailPrompt() {
    document.getElementById('email-prompt').style.display = 'block';
}

// Send email with attendance data
function sendEmail() {
    const email = document.getElementById('email').value;
    fetch(`/send_email/{{ class_name }}?email=${email}`)
        .then(response => response.json())
        .then(data => {
            alert(data.message);
            document.getElementById('email-prompt').style.display = 'none';
        });
}
