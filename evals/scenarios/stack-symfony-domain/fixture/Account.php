<?php

namespace App\Entity;

use Doctrine\ORM\Mapping as ORM;

#[ORM\Entity]
class Account
{
    #[ORM\Id]
    #[ORM\GeneratedValue]
    #[ORM\Column]
    private ?int $id = null;

    #[ORM\Column]
    private string $plan = 'free';

    #[ORM\Column]
    private bool $billingHealthy = true;

    #[ORM\Column]
    private int $workspaceCount = 0;

    public function isPremiumEligible(): bool
    {
        // business rule currently lives on the Doctrine entity
        return $this->plan !== 'free'
            && $this->billingHealthy
            && $this->workspaceCount < 3;
    }

    public function getId(): ?int
    {
        return $this->id;
    }
}
