// nftycoon.rs

use solana_program::{
    account_info::{next_account_info, AccountInfo},
    entrypoint,
    entrypoint::ProgramResult,
    msg,
    pubkey::Pubkey,
    program_error::ProgramError,
    program_pack::{Pack, IsInitialized},
    sysvar::{rent::Rent, Sysvar},
};
use borsh::{BorshDeserialize, BorshSerialize};

// Define the NFT metadata structure
#[derive(BorshSerialize, BorshDeserialize, Debug, Default)]
struct NFTMetadata {
    name: String,
    description: String,
    // Add more metadata fields as needed
}

// Define the NFT structure
#[derive(BorshSerialize, BorshDeserialize, Debug)]
struct NFT {
    owner: Pubkey,
    metadata: NFTMetadata,
    is_initialized: bool,
}

impl IsInitialized for NFT {
    fn is_initialized(&self) -> bool {
        self.is_initialized
    }
}

// Entry point for the smart contract
entrypoint!(process_instruction);

pub fn process_instruction(
    program_id: &Pubkey,
    accounts: &[AccountInfo],
    instruction_data: &[u8],
) -> ProgramResult {
    // Split the accounts into mutable and immutable references
    let accounts_iter = &mut accounts.iter();
    let nft_account = next_account_info(accounts_iter)?;

    if !nft_account.is_writable {
        msg!("NFT account must be writable");
        return Err(ProgramError::InvalidAccountData);
    }

    // Initialize a Rent sysvar to check rent exemption
    let rent = &Rent::from_account_info(next_account_info(accounts_iter)?)?;

    // Define the available instructions
    enum Instruction {
        InitializeNFT,
        MintNFT(NFTMetadata),
        TransferNFT(Pubkey),
    }

    let instruction = Instruction::try_from_slice(instruction_data)
        .map_err(|_| ProgramError::InvalidInstructionData)?;

    match instruction {
        Instruction::InitializeNFT => {
            // Ensure that the NFT account is not already initialized
            if nft_account.state().is_initialized() {
                msg!("NFT account is already initialized");
                return Err(ProgramError::AccountAlreadyInitialized);
            }

            // Initialize the NFT account
            let nft_data = NFT {
                owner: *nft_account.owner,
                metadata: NFTMetadata::default(),
                is_initialized: true,
            };

            nft_data.serialize(&mut &mut nft_account.data.borrow_mut())?;
        }
        Instruction::MintNFT(metadata) => {
            // Ensure that the NFT account is initialized
            if !nft_account.state().is_initialized() {
                msg!("NFT account is not initialized");
                return Err(ProgramError::UninitializedAccount);
            }

            // Check if the caller is the owner of the NFT
            if nft_account.owner != program_id {
                msg!("Only the owner can mint NFTs");
                return Err(ProgramError::InvalidAccountData);
            }

            // Check if the NFT account is rent-exempt
            if !rent.is_exempt(nft_account.lamports(), nft_account.data_len()) {
                msg!("NFT account must be rent-exempt");
                return Err(ProgramError::AccountNotRentExempt);
            }

            // Create a new NFT and set its metadata
            let mut nft_data = NFT::try_from_slice(&nft_account.data.borrow())?;
            nft_data.metadata = metadata;

            // Serialize the modified NFT data and save it back to the account
            nft_data.serialize(&mut &mut nft_account.data.borrow_mut())?;
        }
        Instruction::TransferNFT(new_owner) => {
            // Ensure that the NFT account is initialized
            if !nft_account.state().is_initialized() {
                msg!("NFT account is not initialized");
                return Err(ProgramError::UninitializedAccount);
            }

            // Check if the caller is the current owner of the NFT
            if nft_account.owner != program_id {
                msg!("Only the owner can transfer NFTs");
                return Err(ProgramError::InvalidAccountData);
            }

            // Transfer the NFT to the new owner
            nft_account.set_owner(new_owner)?;
        }
    }

    Ok(())
}
