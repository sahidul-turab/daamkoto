// Cloudflare Worker — serves the daamkoto-images R2 bucket without the r2.dev
// rate limit. Bind the bucket as `BUCKET` (Settings -> Bindings -> R2 bucket).
// Public URL becomes: https://<worker>.<subdomain>.workers.dev/cutouts/<hash>.png
export default {
  async fetch(request, env) {
    const key = decodeURIComponent(new URL(request.url).pathname.slice(1));
    if (!key) return new Response("Not found", { status: 404 });

    const object = await env.BUCKET.get(key);
    if (!object) return new Response("Not found", { status: 404 });

    const headers = new Headers();
    object.writeHttpMetadata(headers);
    headers.set("etag", object.httpEtag);
    headers.set("Cache-Control", "public, max-age=31536000, immutable");
    headers.set("Access-Control-Allow-Origin", "*");
    return new Response(object.body, { headers });
  },
};
