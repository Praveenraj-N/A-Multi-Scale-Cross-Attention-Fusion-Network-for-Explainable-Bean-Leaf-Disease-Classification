// Browser geolocation with explicit, human-readable failure reasons.
// The browser asks the user for permission; nothing is read until they agree.

export function getBrowserLocation({ timeoutMs = 10000 } = {}) {
  return new Promise((resolve, reject) => {
    if (typeof navigator === "undefined" || !navigator.geolocation) {
      reject(new Error("This browser doesn't support location. Enter coordinates or pick a registered plantation instead."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lon: pos.coords.longitude, accuracyM: pos.coords.accuracy }),
      (err) => {
        const messages = {
          1: "Location permission was denied. Enter coordinates manually or pick a registered plantation instead.",
          2: "Your position couldn't be determined. Enter coordinates manually instead.",
          3: "Finding your position timed out. Try again or enter coordinates manually."
        };
        reject(new Error(messages[err.code] ?? "Couldn't get your location."));
      },
      { enableHighAccuracy: true, timeout: timeoutMs, maximumAge: 60000 }
    );
  });
}
