import fastapi
from models.user import UserCreate, UserUpdate, UserResponse
from api.auth import get_current_user, require_role
from controllers.user_controller import (
    create_user_controller,
    get_user_controller,
    list_users_controller,
    update_user_controller,
    delete_user_controller,
)

router = fastapi.APIRouter()


@router.get("/users/{user_id}", response_model=UserResponse, dependencies=[fastapi.Depends(get_current_user)])
def get_user(user_id: str):
    user = get_user_controller(user_id)
    return UserResponse(**user)

@router.get("/users/", dependencies=[fastapi.Depends(get_current_user)])
def list_users():
    users = list_users_controller()
    return [UserResponse(**user) for user in users]

@router.put("/users/{user_id}", response_model=UserResponse, dependencies=[fastapi.Depends(require_role("Admin"))])
def update_user(user_id: str, user: UserUpdate):
    updated_user = update_user_controller(user_id, user)
    return UserResponse(**updated_user)

@router.delete("/users/{user_id}", dependencies=[fastapi.Depends(require_role("Admin"))])
def delete_user(user_id: str):
    delete_user_controller(user_id)
    return {"detail": "User deleted successfully"}