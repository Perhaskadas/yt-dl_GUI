document.getElementById("btn").addEventListener("click", async () => {
  const r = await pywebview.api.ping();
  document.getElementById("out").textContent = r;
});