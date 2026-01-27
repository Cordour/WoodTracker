import "dotenv/config";

export async function getAccessToken() {
  const CLIENT_ID = process.env.BLIZZARD_CLIENT_ID;
  const CLIENT_SECRET = process.env.BLIZZARD_CLIENT_SECRET;

  if (!CLIENT_ID || !CLIENT_SECRET) {
    throw new Error("Missing BLIZZARD_CLIENT_ID or BLIZZARD_CLIENT_SECRET");
  }

  const res = await fetch("https://oauth.battle.net/token", {
    method: "POST",
    headers: {
      Authorization:
        "Basic " +
        Buffer.from(`${CLIENT_ID}:${CLIENT_SECRET}`).toString("base64"),
      "Content-Type": "application/x-www-form-urlencoded"
    },
    body: "grant_type=client_credentials"
  });

  if (!res.ok) {
    throw new Error("OAuth token error");
  }

  const data = await res.json();
  return data.access_token;
}
