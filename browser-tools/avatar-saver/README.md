# LAN42 — save this avatar

This local Manifest V3 Chrome extension saves the pixels of a photo the owner has
already opened successfully. It does not fetch 42 again, read cookies, attach to
a browser profile or bypass challenges. It does not save screenshots of a tab.

## One-time installation (user action required)

Open `chrome://extensions`, enable Developer mode, choose **Load unpacked**, and
select this directory. Pin **LAN42 — save this avatar** in the extension menu.
If your managed browser disallows unpacked extensions, keep the manual importer;
this tool does not change enterprise policy.

Permissions are `activeTab`, `scripting`, and `downloads`. The first two allow a
user-invoked action on the active tab. `downloads` permits saving the captured
PNG; Chrome grants broader download-management capability with that permission,
but this code never queries or modifies unrelated downloads. There are no host,
cookies, browsing-history, webRequest, debugger or native-messaging permissions.

## Use

1. On the master computer open LAN42 `/admin`.
2. Enter the Intra login and choose **Prepare one-click save**.
3. Click the prepared photo link. It carries a short-lived random import-job ID
   in its fragment, which is not sent to the CDN.
4. Once that tab displays the actual photo, click the extension icon.
5. The extension exports only that same-origin image through a canvas, scaled to
   at most 512 pixels per side, and downloads a PNG under
   `Downloads/lan42-avatar-imports/JOB_ID.png`.
6. The open admin tool watches only that exact authorized filename, validates it,
   moves the image into the private cache and removes the temporary download.
   In FORKNITE choose **Reload cached photo**.

The job expires after ten minutes. The owner must keep the admin process open.
Chrome's default download location must match the desktop Downloads directory
shown in the admin panel. If it differs, use the manual file picker/drop path.
If the admin process closes before import, the temporary file remains in its
private staging folder and can be imported manually; unrelated downloads are
never scanned, read or deleted.

A challenge/error page or a tainted image cannot be captured. The extension gives
an error rather than attempting to bypass browser security. Top-level PNG/JPEG
navigation with ordinary same-origin canvas export was verified in real Chrome
using a local intercepted fixture. Saving an actual 42 photo requires the user
to open it successfully in their normal browser and install this extension.
