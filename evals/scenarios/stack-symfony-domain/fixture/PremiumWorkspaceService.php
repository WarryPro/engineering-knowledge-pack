<?php

namespace App\Service;

use App\Entity\Account;
use Doctrine\ORM\EntityManagerInterface;
use Symfony\Bundle\SecurityBundle\Security;

class PremiumWorkspaceService
{
    public function __construct(
        private EntityManagerInterface $em,
        private Security $security,
    ) {
    }

    public function openForAccount(Account $account): string
    {
        if ($this->security->getUser() !== $account) {
            throw new \RuntimeException('Token account mismatch');
        }
        if (!$account->isPremiumEligible()) {
            throw new \RuntimeException('Not eligible');
        }
        // persistence + side effects omitted
        return 'ws_' . $account->getId();
    }
}
