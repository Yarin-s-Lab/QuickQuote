import { describe, expect, it } from "vitest";
import { partiesSchema } from "./types";

const valid = {
  agent_name: "דנה כהן",
  client_full_name: "ישראל ישראלי",
  client_phone: "",
  client_email: "",
};

describe("partiesSchema", () => {
  it("accepts required names with empty optional fields", () => {
    expect(partiesSchema.safeParse(valid).success).toBe(true);
  });

  it("accepts a valid phone and email", () => {
    const result = partiesSchema.safeParse({
      ...valid,
      client_phone: "050-1234567",
      client_email: "client@example.com",
    });
    expect(result.success).toBe(true);
  });

  it.each([
    ["agent_name", "", "יש להזין שם סוכן"],
    ["agent_name", "   ", "יש להזין שם סוכן"],
    ["client_full_name", "", "יש להזין שם לקוח"],
    ["client_full_name", "א".repeat(101), "עד 100 תווים"],
    ["client_phone", "abc", "מספר טלפון לא תקין"],
    ["client_email", "not-an-email", 'כתובת דוא"ל לא תקינה'],
  ])("rejects %s=%j", (field, value, message) => {
    const result = partiesSchema.safeParse({ ...valid, [field]: value });
    expect(result.success).toBe(false);
    expect(result.error?.issues[0].message).toBe(message);
    expect(result.error?.issues[0].path).toEqual([field]);
  });

  it("allows exactly 100 characters", () => {
    expect(partiesSchema.safeParse({ ...valid, agent_name: "א".repeat(100) }).success).toBe(true);
  });
});
