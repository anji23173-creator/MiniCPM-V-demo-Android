#!/usr/bin/env bash
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
HARNESS_ROOT="${HARNESS_ROOT:-${SCRIPT_DIR}/data}"
DEFAULT_MODEL_ID="${DEFAULT_MODEL_ID:-llama-3.2-1b-instruct}"
LAST_SESSION_ID=""

cd "${REPO_ROOT}"

run_cli() {
  "${PYTHON_BIN}" -m harness_logic --root "${HARNESS_ROOT}" "$@"
}

remember_session_id() {
  LAST_SESSION_ID="$("${PYTHON_BIN}" -c 'import json,sys; print(json.load(sys.stdin)["session_id"])' <<< "$1")"
}

pause() {
  printf "\n按 Enter 返回菜单..."
  read -r _unused
}

print_header() {
  clear 2>/dev/null || true
  cat <<EOF
Harness Logic

项目目录: harness_logic/
运行目录: ${HARNESS_ROOT/#${REPO_ROOT}/.}
Python: ${PYTHON_BIN}

EOF
}

show_menu() {
  cat <<'EOF'
请选择要执行的操作：

  1. 列出当前注册模型
  2. 查看当前选中模型状态
  3. 查看某个模型的完整 spec
  4. 选择模型
  5. 查看当前选中模型的下载计划
  6. 初始化 mock demo 文件
  7. 发送一条 mock 对话消息
  8. 自动运行完整 mock demo
  9. 加载当前选中模型到 mock backend
 10. 迁移旧模型目录结构
 11. 删除当前选中模型 artifact 文件
 12. 运行单元测试
 13. 运行 Python 语法检查
 14. 透传到底层 Python CLI
 15. 列出当前注册角色
 16. 通过编号选择角色并查看信息
 17. 校验内置角色包
 18. 编译角色 Prompt
 19. 运行 mock 角色对话
 20. 新建角色会话
 21. 在会话中运行 mock 角色对话
 22. 查看角色会话
 23. 列出 Memory
 24. 新增 Memory
 25. 搜索 Memory

输入 q / quit / exit 退出，也可以按 Ctrl+C 退出。
EOF
}

choose_model_id() {
  local prompt="${1:-请选择模型编号}"
  local default_id="${2:-${DEFAULT_MODEL_ID}}"
  local model_id display_name family capabilities artifacts
  local selected
  local default_index=""
  local index=1
  local model_ids=()
  local model_names=()

  echo "当前可用模型：" >&2
  while IFS=$'\t' read -r model_id display_name family capabilities artifacts; do
    model_ids+=("${model_id}")
    model_names+=("${display_name}")
    if [[ "${model_id}" == "${default_id}" ]]; then
      default_index="${index}"
    fi
    printf " %2d. %s  [%s | %s]\n" "${index}" "${display_name}" "${family}" "${capabilities}" >&2
    printf "     id: %s\n" "${model_id}" >&2
    index=$((index + 1))
  done < <(run_cli list)

  if [[ ${#model_ids[@]} -eq 0 ]]; then
    echo "没有可用模型。" >&2
    return 1
  fi

  if [[ -z "${default_index}" ]]; then
    default_index="1"
  fi

  while true; do
    printf "%s [%s]: " "${prompt}" "${default_index}" >&2
    read -r selected
    selected="${selected:-${default_index}}"
    if [[ "${selected}" =~ ^[0-9]+$ ]] && (( selected >= 1 && selected <= ${#model_ids[@]} )); then
      echo "${model_ids[$((selected - 1))]}"
      return 0
    fi
    echo "编号无效，请输入 1-${#model_ids[@]} 之间的数字。" >&2
  done
}

read_message() {
  local default="${1:-你好}"
  local message
  printf "请输入消息 [%s]: " "${default}" >&2
  read -r message
  echo "${message:-${default}}"
}

read_optional() {
  local prompt="$1"
  local default="${2:-}"
  local value
  if [[ -n "${default}" ]]; then
    printf "%s [%s]: " "${prompt}" "${default}" >&2
  else
    printf "%s: " "${prompt}" >&2
  fi
  read -r value
  echo "${value:-${default}}"
}

choose_character_id() {
  local prompt="${1:-请选择角色编号}"
  local selected
  local index character_id display_name pack_id story_cutoff aliases
  local character_ids=()

  echo "当前可用角色：" >&2
  while IFS=$'\t' read -r index character_id display_name pack_id story_cutoff aliases; do
    character_ids+=("${character_id}")
    printf " %2d. %s  [%s]\n" "${index}" "${display_name}" "${pack_id}" >&2
    printf "     id: %s  cutoff: %s\n" "${character_id}" "${story_cutoff}" >&2
    if [[ -n "${aliases}" ]]; then
      printf "     aliases: %s\n" "${aliases}" >&2
    fi
  done < <(run_cli character-list)

  if [[ ${#character_ids[@]} -eq 0 ]]; then
    echo "没有可用角色。" >&2
    return 1
  fi

  while true; do
    printf "%s [1]: " "${prompt}" >&2
    read -r selected
    selected="${selected:-1}"
    if [[ "${selected}" =~ ^[0-9]+$ ]] && (( selected >= 1 && selected <= ${#character_ids[@]} )); then
      echo "${character_ids[$((selected - 1))]}"
      return 0
    fi
    echo "编号无效，请输入 1-${#character_ids[@]} 之间的数字。" >&2
  done
}

run_action() {
  local choice="$1"
  local model_id
  local character_id
  local message
  local raw_args

  case "${choice}" in
    1|list)
      run_cli list
      ;;
    2|status)
      run_cli status
      ;;
    3|spec)
      model_id="$(choose_model_id "请输入要查看的模型编号")"
      run_cli spec "${model_id}"
      ;;
    4|select)
      model_id="$(choose_model_id "请输入要选择的模型编号")"
      run_cli select "${model_id}"
      ;;
    5|plan|download-plan)
      run_cli download-plan
      ;;
    6|init-demo)
      model_id="$(choose_model_id "请输入 demo 模型编号")"
      run_cli select "${model_id}"
      run_cli touch-demo-files
      ;;
    7|chat|prompt)
      message="$(read_message "你好")"
      run_cli prompt "${message}"
      ;;
    8|demo)
      model_id="$(choose_model_id "请输入 demo 模型编号")"
      message="$(read_message "你好")"
      run_cli select "${model_id}"
      run_cli touch-demo-files
      run_cli prompt "${message}"
      ;;
    9|load)
      run_cli load
      ;;
    10|migrate)
      run_cli migrate
      ;;
    11|delete)
      run_cli delete
      ;;
    12|test)
      "${PYTHON_BIN}" -m unittest discover -s harness_logic/tests -v
      ;;
    13|check)
      "${PYTHON_BIN}" -m py_compile harness_logic/*.py harness_logic/backends/*.py harness_logic/tests/*.py
      ;;
    14|raw)
      printf "请输入底层 CLI 参数，例如 list 或 spec <model_id>: "
      read -r raw_args
      if [[ -z "${raw_args}" ]]; then
        echo "未输入参数。"
      else
        # shellcheck disable=SC2086
        run_cli ${raw_args}
      fi
      ;;
    15|character-list)
      run_cli character-list
      ;;
    16|character-select)
      character_id="$(choose_character_id "请输入要查看的角色编号")"
      echo "selected_character_id=${character_id}"
      ;;
    17|character-pack-validate)
      run_cli character-pack validate
      ;;
    18|character-prompt)
      character_id="$(choose_character_id "请输入角色编号")"
      message="$(read_message "玄谙究竟是什么？")"
      run_cli character-prompt --character "${character_id}" --input "${message}"
      ;;
    19|character-chat)
      character_id="$(choose_character_id "请输入角色编号")"
      model_id="$(choose_model_id "请输入模型编号")"
      message="$(read_message "你好")"
      run_cli character-chat \
        --backend mock \
        --model "${model_id}" \
        --character "${character_id}" \
        --input "${message}" \
        --touch-demo-files
      ;;
    20|session-new)
      character_id="$(choose_character_id "请输入角色编号")"
      model_id="$(choose_model_id "请输入模型编号")"
      cutoff="$(read_optional "请输入剧情 cutoff，必须是 evt-001 这类事件 ID；直接回车使用默认值" "evt-018")"
      session_json="$(run_cli session-new --character "${character_id}" --model "${model_id}" --cutoff "${cutoff}")"
      echo "${session_json}"
      remember_session_id "${session_json}"
      echo "已记住最近 session_id=${LAST_SESSION_ID}"
      ;;
    21|session-chat)
      session_id="$(read_optional "请输入 session_id" "${LAST_SESSION_ID}")"
      if [[ -z "${session_id}" ]]; then
        echo "session_id 不能为空。请先选择 20 新建角色会话，或输入已有 session_id。"
        return 0
      fi
      LAST_SESSION_ID="${session_id}"
      message="$(read_message "你好")"
      run_cli session-chat --session "${session_id}" --input "${message}" --touch-demo-files
      ;;
    22|session-show)
      session_id="$(read_optional "请输入 session_id" "${LAST_SESSION_ID}")"
      if [[ -z "${session_id}" ]]; then
        echo "session_id 不能为空。请先选择 20 新建角色会话，或输入已有 session_id。"
        return 0
      fi
      LAST_SESSION_ID="${session_id}"
      run_cli session-show --session "${session_id}"
      ;;
    23|memory-list)
      session_id="$(read_optional "按 session_id 过滤，留空则不过滤" "${LAST_SESSION_ID}")"
      if [[ -n "${session_id}" ]]; then
        run_cli memory-list --session "${session_id}"
      else
        run_cli memory-list
      fi
      ;;
    24|memory-add)
      character_id="$(choose_character_id "请输入角色编号")"
      session_id="$(read_optional "可选 session_id，留空则写角色长期 memory")"
      message="$(read_optional "请输入 memory 内容")"
      if [[ -n "${session_id}" ]]; then
        run_cli memory-add --character "${character_id}" --session "${session_id}" --text "${message}"
      else
        run_cli memory-add --character "${character_id}" --kind character_memory --text "${message}"
      fi
      ;;
    25|memory-search)
      character_id="$(choose_character_id "请输入角色编号")"
      message="$(read_optional "请输入搜索内容")"
      run_cli memory-search --character "${character_id}" --query "${message}"
      ;;
    q|quit|exit)
      echo "已退出。"
      exit 0
      ;;
    "")
      echo "未输入操作。"
      ;;
    *)
      echo "未知操作：${choice}"
      ;;
  esac
}

trap 'printf "\n已退出。\n"; exit 0' INT

while true; do
  print_header
  show_menu
  printf "\n请选择: "
  read -r choice || {
    printf "\n已退出。\n"
    exit 0
  }
  printf "\n"
  run_action "${choice}"
  pause
done
