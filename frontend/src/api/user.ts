import type { CancelToken } from "axios";
import api from ".";
import { type LoginResponse } from "./types";

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
