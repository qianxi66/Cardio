import type { CancelToken } from "axios";
import api from ".";
import { type LoginResponse, type UserInfoResponse } from "./types";

export const login = async (
  username: string,
  password: string,
  rememberme: boolean,
) => {
  return (await api({
    url: "/login",
    method: "POST",
    data: { username, password, rememberme },
    validateStatus: () => true,
  })) as LoginResponse;
};
export const getUserInfo = async (token: string) => {
  return (await api({
    url: "/get_user_info",
    method: "GET",
    headers: {
      Authorization: `Bearer ${token}`,
    },
    validateStatus: () => true,
  })) as UserInfoResponse;
};
