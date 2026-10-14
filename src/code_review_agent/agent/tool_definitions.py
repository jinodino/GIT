TOOLS = [
     {
        "type": "function",
        "name": "read_file",
        "description": "프로젝트 내부 Python 파일을 읽습니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "프로젝트 루트 기준 상대 경로"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "search_code",
        "description": "프로젝트 내 Python 코드에서 문자열을 검색합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "검색할 코드 또는 함수 이름"
                }
            },
            "required": ["keyword"],
            "additionalProperties": False
        },
        "strict": True
    },
    {
        "type": "function",
        "name": "run_ruff",
        "description": "Python 파일에 Ruff 정적 분석을 실행합니다.",
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "분석할 Python 파일의 상대 경로"
                }
            },
            "required": ["file_path"],
            "additionalProperties": False
        },
        "strict": True
    }
]