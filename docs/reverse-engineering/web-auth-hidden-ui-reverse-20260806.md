# SR1010 Web 认证、敏感字段加密与隐藏升级页逆向

日期：2026-08-06  
固件：`V1.0.0.2B5.8000`

## 登录协议已完整复现

Vue 前端及实机响应共同确认：

1. `GET /?_type=loginsceneData&_tag=login_token_json`
2. 返回 `_sessionToken` 与 8 位十进制 `logintoken`
3. 客户端计算：

```text
Password = hex(SHA256(plaintext_password + logintoken))
```

4. POST `/?_type=loginData&_tag=login_entry`：

```text
Username=admin
Password=<proof>
action=login
Frm_Logintoken=
captchaCode=
_sessionTOKEN=<第一步的_sessionToken>
```

5. 成功响应返回 `sess_token`，Cookie 为 `SID_HTTPS_`、`HttpOnly`、`Secure`、`SameSite=Strict`。

首次手工复现漏传 `_sessionTOKEN` 时，服务端明确返回 `e_csrf_check_fail`。加入该字段后成功。这证明 token 与 Cookie/登录事务绑定，不是只校验密码哈希。

新增只读客户端：[`tools/web-login-readonly.py`](tools/web-login-readonly.py)。它只实现登录和 GET，不提供任意配置写入方法，密码通过交互输入，避免进入仓库。

## CSRF/session 行为

前端 Axios 拦截器对每个 POST 自动追加：

```text
_sessionTOKEN=g_sessionTmpToken
```

响应头若出现 `x_xsrf_token`，前端立即用它替换当前 token。登录响应中的 `sess_token` 也是后续 token 初值。GET 主要依赖 session Cookie；敏感 POST 同时需要 Cookie 和当前 session token。

## 两套密码保护机制

### 登录密码 proof

登录本身不使用 RSA，只使用 `SHA256(password + logintoken)`。它是一次性挑战响应，但服务器证书和 HTTPS 仍是传输层保障。

### 配置中的敏感字段

修改管理密码、Wi-Fi 密码、PPPoE 密码等使用另一套 envelope：

1. 生成两个 16 位十进制随机串 `keySeed`、`ivSeed`；
2. `AESKey = SHA256(keySeed)`；
3. `AESIV = SHA256(ivSeed)`，CryptoJS CBC 实际使用 AES 所需的 IV 部分；
4. 敏感字段使用 AES-CBC + ZeroPadding；
5. `encode = RSA-PKCS#1-v1.5(publicKey, keySeed + "+" + ivSeed)`；
6. POST 同时携带加密字段和 `encode`。

服务器用上一阶段解出的静态 RSA 私钥恢复种子。读取敏感字段时，设备用当前 `sess_token` 和其逆序串作为 AES 材料返回密文，前端再解密。

因此静态 Web RSA 密钥不是登录密码本身，但控制了 Web 配置敏感字段的 envelope。

## 隐藏升级入口

`hidden_url_map.lua` 明确把：

```text
/supgrade.html
```

映射到 `hidden_upgrade_firmware_t.lp`。实机只读验证：

| 请求 | 未登录 | admin 登录后 |
|---|---|---|
| `/supgrade.html` | 404 包含 `SessionTimeout` | 200，完整固件升级页面 |
| `vuecfg_data` | 404/SessionTimeout | 200 |
| `initial_info_json` | 200，`loginStatus=loginNone` | 200，登录态信息 |
| `vue_userif_data` | 两种状态均 200 | 两种状态均 200 |

结论：隐藏升级页不是免认证后门；它只是未出现在普通导航中的已认证页面。当前唯一 Web 用户 `admin` 的 Level 为 1，已能打开该页，没有观察到额外“超级管理员”门槛。

## 账号和角色

当前配置关键表：

- `DevAuthInfo`：一行，`admin`，Level 1；
- `SFUDevAuthInfo`：一行，`admin`，Level 1；
- `TelnetCfg`：独立的 root 用户、密码、Level 3；
- `FTPUser`：独立 admin，UserRight 3；
- `UserIF`：Web 端口、超时、语言、证书口令等。

Lua 模块把当前 session 的 `login_right` 作为权限来源。`managdiag_account_manag_lua` 在账号修改时比较当前 Right、目标 Right，并在修改自身密码后销毁 session。Web/Telnet/FTP 不是同一个统一 PAM 账号库。

## 公开信息面

未登录即可读取 `initial_info_json` 和 `vue_userif_data`，会暴露：

- 具体型号/CPU/固件版本；
- Web 标题、语言、Mesh 主从模式；
- 登录锁定次数、主机名和部分能力开关；
- 当前 session/login 状态。

目前未在这些匿名响应中看到明文管理密码或私钥，但它们提供了精确的版本和能力指纹。

## 下一步

1. 批量解析 `adaptFunc` 和 Lua 模块，生成 URL → 登录要求 → 对象表 → GET/POST 动作矩阵。
2. 反汇编 `funcs_login`、`SetLogin` 与 session manager，确认 proof 服务端比较和锁定计数。
3. 追踪 `cmd`、`cpeserver`、`hadbgd` 本地消息接口及其调用者权限。
4. 分离真正只读诊断接口与会改变状态的接口，后者不在远程阶段调用。

