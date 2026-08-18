import { describe, expect, it } from "vitest";
import { APP_DESCRIPTION, APP_NAME } from "@/lib/app-config";

describe("app identity", () => {
  it("ships the canonical app name and description", () => {
    expect(APP_NAME).toBe("Immich B2 Backend");
    expect(APP_DESCRIPTION).toBe(
      "Self-hosted photo library backed by Backblaze B2 object storage"
    );
  });
});
