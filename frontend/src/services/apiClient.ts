import axios from "axios";

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim().replace(/\/+$/, "");
const baseURL = import.meta.env.DEV
	? configuredBaseUrl === "/api" ? configuredBaseUrl : "/api"
	: configuredBaseUrl || "/api";

export const apiClient = axios.create({
	baseURL,
	headers: { "Content-Type": "application/json" },
	timeout: 70000,
});