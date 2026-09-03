<?php

namespace App\Controller;

use App\Entity\Account;
use App\Service\PremiumWorkspaceService;
use Symfony\Bundle\FrameworkBundle\Controller\AbstractController;
use Symfony\Component\HttpFoundation\Request;
use Symfony\Component\HttpFoundation\Response;

class PremiumWorkspaceController extends AbstractController
{
    public function open(Request $request, PremiumWorkspaceService $service): Response
    {
        /** @var Account $account */
        $account = $this->getUser();
        if ($request->request->getBoolean('acceptTerms') !== true) {
            $this->addFlash('error', 'Terms required');
            return $this->redirectToRoute('workspace_start');
        }

        if (!$account->isPremiumEligible()) {
            $this->addFlash('error', 'Account is not eligible');
            return $this->redirectToRoute('workspace_start');
        }

        $workspaceId = $service->openForAccount($account);
        return $this->redirectToRoute('workspace_show', ['id' => $workspaceId]);
    }
}
