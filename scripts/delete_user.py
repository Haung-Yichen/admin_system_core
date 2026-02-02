import asyncio
import logging
fromsqlalchemy import select
from core.database.session import get_standalone_session
from core.models.user import User

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    async with get_standalone_session() as session:
        # Check all users
        result = await session.execute(select(User))
        all_users = result.scalars().all()
        logger.info(f"Total users in DB: {len(all_users)}")
        
        for user in all_users:
            logger.info(f"Checking User ID: {user.id}")
            logger.info(f"Ragic ID: {user.ragic_id}")
            
            # Since we strongly suspect this is the failed user (Ragic ID is None)
            # And it's the only one, we will delete it.
            
            try:
                # Try to see email (might fail if key changed)
                email = user.email
                logger.info(f"User email: {email}")
            except Exception as e:
                logger.error(f"Could not decrypt email (Key mismatch?): {e}")

            if user.ragic_id is None:
                logger.info("User has no Ragic ID. Deleting...")
                await session.delete(user)
                await session.commit()
                logger.info("User deleted successfully.")
            else:
                logger.warning("User has Ragic ID, skipping delete.")

if __name__ == "__main__":
    asyncio.run(main())
