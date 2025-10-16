const urlParams = new URLSearchParams(window.location.search);
const url = urlParams.get('url');
if (url) {
    document.getElementById('urlParam').textContent = `URL Parameter: ${url}`;
} else {
    document.getElementById('urlParam').textContent = 'No URL parameter provided.';
}