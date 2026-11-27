import axios from "axios";
import { apiClient } from "./apiClient";
import type { WireframeResponse } from "../types/wireframe";
import { validateWireframe } from "../utils/validateWireframe";

export const generateWireframe = async (
  requirement: string,
): Promise<WireframeResponse> => {
  try {
    const response = await apiClient.post<unknown>("/wireframe/generate", { requirement });

    return validateWireframe(response.data);
  } catch (error: unknown) {
    if (axios.isAxiosError(error)) {
      switch (error.response?.status) {
        case 404:
          throw new Error("The backend endpoint was not found. Check the API routing.");
        case 502:
          throw new Error("The AI returned an invalid result. Please retry.");
        case 503:
          throw new Error("The AI service is temporarily busy. Please retry shortly.");
        case 504:
          throw new Error("The AI response took too long. Please retry.");
        default:
          if (!error.response) {
            throw new Error("The backend is unavailable. Confirm that FastAPI is running.");
          }
      }
    }
    throw error;
  }
};